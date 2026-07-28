"""PDF 원문을 페이지 단위로 보존하고 주장 후보를 선별한다."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import pdfplumber


@dataclass(frozen=True)
class ExtractedTable:
    bbox: tuple[float, float, float, float]
    rows: tuple[tuple[str | None, ...], ...]


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
