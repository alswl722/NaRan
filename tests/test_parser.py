import json
from pathlib import Path

import pytest

from db.parser import (
    PageContent,
    ParsedDocument,
    _value_display_variants,
    find_value_bbox,
    parse_pdf,
    prefilter_claim_candidates,
)


ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "fixtures"
REFERENCES = ROOT / "references"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_case_a_pages_preserve_verified_values_and_hash() -> None:
    case = load("sample_case_a.json")
    document = parse_pdf(
        REFERENCES / "Samsung-Biologics-2025-ESG-Report_KR.pdf",
        pages={171, 172},
    )
    text = "\n".join(page.text for page in document.pages)

    assert document.file_hash == case["report"]["file_hash"]
    assert [page.page for page in document.pages] == [171, 172]
    assert "71,840.290" in text
    assert "154,678.989" in text
    assert all(page.has_text_layer for page in document.pages)


def test_case_b_page_preserves_value_and_global_boundary_footnote() -> None:
    case = load("sample_case_b.json")
    document = parse_pdf(
        REFERENCES / "Samsung_Electronics_Sustainability_Report_2025_ENG.pdf",
        pages={68},
    )
    text = document.pages[0].text

    assert document.file_hash == case["report"]["file_hash"]
    assert "14,889" in text
    assert "Korean and overseas manufacturing subsidiaries" in text


def test_prefilter_keeps_quantified_environment_claims_with_location() -> None:
    document = ParsedDocument(
        path="fixture.pdf",
        file_hash="sha256:test",
        total_pages=1,
        pages=(
            PageContent(
                page=1,
                text=(
                    "회사는 환경경영을 중요하게 생각합니다.\n"
                    "2024년 Scope 1 배출량은 71,840.290 tCO2eq입니다.\n"
                    "문의처 2024-1234"
                ),
                tables=(),
            ),
        ),
    )

    result = prefilter_claim_candidates(document)

    assert result.included_count == 1
    assert result.excluded_count == 2
    assert result.candidates[0].page == 1
    assert result.candidates[0].line == 2
    assert "ghg_unit" in result.candidates[0].matched_signals


def test_page_without_text_is_recorded_in_filter_result() -> None:
    document = ParsedDocument(
        path="scan.pdf",
        file_hash="sha256:test",
        total_pages=1,
        pages=(
            PageContent(
                page=1,
                text="",
                tables=(),
                extraction_errors=("텍스트 레이어가 없거나 비어 있음",),
            ),
        ),
    )

    result = prefilter_claim_candidates(document)

    assert result.pages_without_text == (1,)
    assert result.included_count == 0


def test_year_only_environment_sentence_is_not_a_numeric_claim() -> None:
    document = ParsedDocument(
        path="fixture.pdf",
        file_hash="sha256:test",
        total_pages=1,
        pages=(
            PageContent(
                page=1,
                text="2024년 Scope 1 온실가스 배출 관리 정책을 개정했습니다.",
                tables=(),
            ),
        ),
    )

    result = prefilter_claim_candidates(document)

    assert result.included_count == 0
    assert result.excluded_count == 1


def test_extracted_tables_preserve_page_coordinates() -> None:
    document = parse_pdf(
        REFERENCES / "Samsung_Electronics_Sustainability_Report_2025_ENG.pdf",
        pages={68},
    )

    assert document.pages[0].tables
    assert all(len(table.bbox) == 4 for table in document.pages[0].tables)
    assert any(
        any("14,889" in (cell or "") for row in table.rows for cell in row)
        for table in document.pages[0].tables
    )


@pytest.mark.parametrize("pages", [set(), {0}, {-1}])
def test_invalid_page_selection_is_rejected(pages: set[int]) -> None:
    with pytest.raises(ValueError, match="1 이상의"):
        parse_pdf(
            REFERENCES / "Samsung-Biologics-2025-ESG-Report_KR.pdf",
            pages=pages,
        )


def test_value_display_variants_include_db_padded_and_pdf_comma_forms() -> None:
    """DB Numeric 컬럼이 돌려주는 trailing-zero 패딩값("71840.2900000000")에서
    PDF 원문 표기("71,840.290")를 후보로 재현할 수 있어야 한다."""
    variants = _value_display_variants("71840.2900000000")
    assert "71,840.290" in variants
    assert "71840.290" in variants


def test_value_display_variants_handle_zero_decimal_integer() -> None:
    variants = _value_display_variants("226519.0000000000")
    assert "226,519" in variants
    assert "226519" in variants


def test_value_display_variants_empty_for_blank_value() -> None:
    assert _value_display_variants("") == []
    assert _value_display_variants("-") == []


def test_find_value_bbox_locates_case_a_scope1_value() -> None:
    bbox = find_value_bbox(
        REFERENCES / "Samsung-Biologics-2025-ESG-Report_KR.pdf",
        page=171,
        value="71840.2900000000",
    )
    assert bbox is not None
    assert bbox.x1 > bbox.x0
    assert bbox.bottom > bbox.top
    assert bbox.page_width > 0
    assert bbox.page_height > 0


def test_find_value_bbox_locates_case_a_total_value() -> None:
    bbox = find_value_bbox(
        REFERENCES / "Samsung-Biologics-2025-ESG-Report_KR.pdf",
        page=220,
        value="226519.0000000000",
    )
    assert bbox is not None


def test_find_value_bbox_locates_case_b_value() -> None:
    bbox = find_value_bbox(
        REFERENCES / "Samsung_Electronics_Sustainability_Report_2025_ENG.pdf",
        page=68,
        value="14889.0000000000",
    )
    assert bbox is not None


def test_find_value_bbox_returns_none_for_absent_value() -> None:
    bbox = find_value_bbox(
        REFERENCES / "Samsung-Biologics-2025-ESG-Report_KR.pdf",
        page=171,
        value="999999999",
    )
    assert bbox is None


def test_find_value_bbox_returns_none_for_out_of_range_page() -> None:
    bbox = find_value_bbox(
        REFERENCES / "Samsung-Biologics-2025-ESG-Report_KR.pdf",
        page=99999,
        value="71840.290",
    )
    assert bbox is None
