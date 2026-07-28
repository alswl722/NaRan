"""PDF 원문을 페이지 단위로 보존하고 주장 후보를 선별한다."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import pdfplumber


@dataclass(frozen=True)
class PageContent:
    page: int
    text: str
    tables: tuple[tuple[tuple[str | None, ...], ...], ...]
    extraction_error: str | None = None

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
            try:
                text = page.extract_text(layout=True) or ""
                tables = tuple(
                    _normalize_table(table) for table in page.extract_tables()
                )
                error = None if text.strip() else "텍스트 레이어가 없거나 비어 있음"
            except (ValueError, TypeError, IndexError) as exc:
                text = ""
                tables = ()
                error = f"{type(exc).__name__}: {exc}"
            extracted.append(
                PageContent(
                    page=page_number,
                    text=text,
                    tables=tables,
                    extraction_error=error,
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
            has_quantity = bool(
                {"number", "percent", "ghg_unit"} & set(matched)
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
