"""PDF 원문을 페이지 단위로 보존하고 주장 후보를 선별한다."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pdfplumber


@dataclass(frozen=True)
class ExtractedTable:
    bbox: tuple[float, float, float, float]
    rows: tuple[tuple[str | None, ...], ...]


@dataclass(frozen=True)
class TextBbox:
    """PDF 좌표계(포인트, 좌상단 원점) 기준 단어 하나의 위치."""

    x0: float
    top: float
    x1: float
    bottom: float
    page_width: float
    page_height: float


@dataclass(frozen=True)
class PageContent:
    page: int
    text: str
    tables: tuple[ExtractedTable, ...]
    extraction_errors: tuple[str, ...] = ()

    @property
    def has_text_layer(self) -> bool:
        return bool(self.text.strip())


@dataclass(frozen=True)
class ParsedDocument:
    path: str
    file_hash: str
    total_pages: int
    pages: tuple[PageContent, ...]


@dataclass(frozen=True)
class ClaimCandidate:
    page: int
    line: int
    raw_text: str
    matched_signals: tuple[str, ...]


@dataclass(frozen=True)
class CandidateFilterResult:
    candidates: tuple[ClaimCandidate, ...]
    included_count: int
    excluded_count: int
    pages_without_text: tuple[int, ...]


_SIGNALS = {
    "year": re.compile(r"\b20\d{2}\b"),
    "number": re.compile(r"(?<!\w)[+-]?\d[\d,]*(?:\.\d+)?"),
    "percent": re.compile(r"%|퍼센트"),
    "ghg_unit": re.compile(
        r"t(?:on(?:nes?)?)?\s*CO[₂2]\s*e?q?|"
        r"(?:천|1,?000)\s*(?:tonnes?|t)\s*CO[₂2]\s*e",
        re.IGNORECASE,
    ),
    "claim_term": re.compile(
        r"감축|배출|온실가스|Scope|GHG|emission|reduction",
        re.IGNORECASE,
    ),
}

_TABLE_SETTINGS = {
    "vertical_strategy": "text",
    "horizontal_strategy": "text",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _normalize_table(
    table: list[list[str | None]],
) -> tuple[tuple[str | None, ...], ...]:
    return tuple(
        tuple(cell.strip() if isinstance(cell, str) else None for cell in row)
        for row in table
    )


def _error(stage: str, exc: Exception) -> str:
    return f"{stage}: {type(exc).__name__}: {exc}"


def parse_pdf(
    path: str | Path,
    *,
    pages: set[int] | None = None,
) -> ParsedDocument:
    """PDF를 1부터 시작하는 페이지 번호와 함께 추출한다."""

    pdf_path = Path(path)
    if not pdf_path.is_file():
        raise FileNotFoundError(pdf_path)
    if pages is not None and (not pages or any(page < 1 for page in pages)):
        raise ValueError("pages에는 1 이상의 페이지 번호가 필요합니다")

    extracted: list[PageContent] = []
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        if pages is not None and max(pages) > total_pages:
            raise ValueError(f"PDF는 {total_pages}페이지까지 존재합니다")
        selected = pages or set(range(1, total_pages + 1))
        for page_number in sorted(selected):
            page = pdf.pages[page_number - 1]
            errors: list[str] = []
            try:
                text = page.extract_text(layout=True) or ""
            except Exception as exc:  # PDF 라이브러리의 페이지별 실패를 격리한다.
                text = ""
                errors.append(_error("텍스트 추출 실패", exc))
            if not text.strip() and not errors:
                errors.append("텍스트 레이어가 없거나 비어 있음")

            extracted_tables: list[ExtractedTable] = []
            try:
                for table in page.find_tables(table_settings=_TABLE_SETTINGS):
                    rows = table.extract()
                    extracted_tables.append(
                        ExtractedTable(
                            bbox=tuple(float(value) for value in table.bbox),
                            rows=_normalize_table(rows),
                        )
                    )
            except Exception as exc:  # 텍스트 성공 여부와 무관하게 표 실패만 기록한다.
                errors.append(_error("표 추출 실패", exc))
            extracted.append(
                PageContent(
                    page=page_number,
                    text=text,
                    tables=tuple(extracted_tables),
                    extraction_errors=tuple(errors),
                )
            )
    return ParsedDocument(
        path=str(pdf_path),
        file_hash=_sha256(pdf_path),
        total_pages=total_pages,
        pages=tuple(extracted),
    )


def prefilter_claim_candidates(
    document: ParsedDocument,
) -> CandidateFilterResult:
    """수치와 환경 주장 표현이 함께 있는 줄만 LLM 입력 후보로 남긴다."""

    candidates: list[ClaimCandidate] = []
    excluded_count = 0
    pages_without_text: list[int] = []
    for page in document.pages:
        if not page.has_text_layer:
            pages_without_text.append(page.page)
            continue
        for line_number, raw_line in enumerate(page.text.splitlines(), start=1):
            line = " ".join(raw_line.split())
            if not line:
                continue
            matched = tuple(
                name for name, pattern in _SIGNALS.items() if pattern.search(line)
            )
            quantity_text = re.sub(
                r"scope\s*[123](?:\s*\+\s*[123])*",
                "",
                line,
                flags=re.IGNORECASE,
            )
            numeric_tokens = _SIGNALS["number"].findall(quantity_text)
            has_non_year_number = any(
                not re.fullmatch(r"20\d{2}", token.replace(",", ""))
                for token in numeric_tokens
            )
            has_quantity = (
                "percent" in matched
                or "ghg_unit" in matched
                or has_non_year_number
            )
            if "claim_term" in matched and has_quantity:
                candidates.append(
                    ClaimCandidate(
                        page=page.page,
                        line=line_number,
                        raw_text=line,
                        matched_signals=matched,
                    )
                )
            else:
                excluded_count += 1
    return CandidateFilterResult(
        candidates=tuple(candidates),
        included_count=len(candidates),
        excluded_count=excluded_count,
        pages_without_text=tuple(pages_without_text),
    )


_MAX_DECIMAL_PLACES_TRIED = 4


def _value_display_variants(value: str) -> list[str]:
    """"71840.2900000000" 같은 DB 조회 문자열에서 PDF 표기 후보를 만든다.

    DB의 Numeric 컬럼은 원본 fixture의 표시 정밀도("71840.290", 소수
    3자리)를 보존하지 않고 trailing zero를 붙여 돌려준다(예:
    "71840.2900000000") — 원본 표시 자릿수 정보는 이 시점에 이미
    사라졌다. 그래서 유효숫자만 남긴 뒤(Decimal.normalize), 실제 PDF가
    어떤 소수 자릿수로 표기했는지 몰라 0~4자리를 전부 시도한다. PDF
    원문은 천 단위 콤마를 포함해 하나의 토큰으로 나오므로 콤마 유무
    두 가지 표기 모두 후보에 넣는다.
    """

    if not value or value == "-":
        return []
    try:
        normalized = Decimal(value).normalize()
    except InvalidOperation:
        return [value]

    variants: set[str] = set()
    # 정수화된 Decimal(예: 226519)은 normalize()가 지수 표기(2.26519E+5)로
    # 바뀔 수 있어 quantize(0)으로 되돌린다.
    base = normalized.quantize(Decimal(1)) if normalized == normalized.to_integral_value() else normalized
    exponent = -base.as_tuple().exponent if base.as_tuple().exponent < 0 else 0

    for places in range(exponent, _MAX_DECIMAL_PLACES_TRIED + 1):
        candidate = base if places == exponent else base.quantize(Decimal(1).scaleb(-places))
        plain = format(candidate, "f")
        whole, _, fraction = plain.partition(".")
        negative = whole.startswith("-")
        digits = whole.lstrip("-")
        if not digits.isdigit():
            continue
        with_commas = f"{'-' if negative else ''}{int(digits):,}"
        with_commas_full = f"{with_commas}.{fraction}" if fraction else with_commas
        variants.add(plain)
        variants.add(with_commas_full)
    return sorted(variants, key=len, reverse=True)


def find_value_bbox(
    path: str | Path,
    *,
    page: int,
    value: str,
) -> TextBbox | None:
    """PDF의 특정 페이지에서 value와 일치하는 단어 토큰의 좌표를 찾는다.

    claim.raw_text 전체를 찾지 않는 이유: fixture의 raw_text는 PDF 원문
    그대로가 아니라 사람이 표를 보고 요약한 문장이라(예: 실제 PDF는 연도별
    수치가 한 줄에 나열된 표, raw_text는 "Scope 1 배출량 — 국내 사업장 —
    2024 — 71,840.290tCO2eq" 같은 정규화 문장) 문장 단위 매칭은 원리적으로
    실패한다. 반면 숫자값은 PDF에 그대로 존재하므로 값 단위 매칭이 더
    신뢰할 수 있다.
    """

    variants = _value_display_variants(value)
    if not variants:
        return None
    with pdfplumber.open(path) as pdf:
        if page < 1 or page > len(pdf.pages):
            return None
        pdf_page = pdf.pages[page - 1]
        words = pdf_page.extract_words()
        for candidate in variants:
            for word in words:
                if word["text"] == candidate:
                    return TextBbox(
                        x0=word["x0"],
                        top=word["top"],
                        x1=word["x1"],
                        bottom=word["bottom"],
                        page_width=float(pdf_page.width),
                        page_height=float(pdf_page.height),
                    )
    return None
