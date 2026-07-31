import json
from datetime import datetime
from pathlib import Path

from api.agent.document_extract import extract_document_page
from api.agent.llm_extract import VerifiedClaimCache
from api.agent.orchestrator import RunLock, RunState
from naran.contracts import ExecutionMode, Report


ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "fixtures"
REFERENCES = ROOT / "references"
NOW = datetime.fromisoformat("2026-07-28T12:00:00+09:00")


class CapturingClient:
    model_name = "gemini-3.6-flash"
    prompt_version = "claim-extract-v3"

    def __init__(self) -> None:
        self.candidate_texts: tuple[str, ...] = ()

    def extract(self, *, candidate_texts, page, output_schema) -> str:
        self.candidate_texts = candidate_texts
        return '{"claims":[]}'


def case(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_verified_case_a_page_runs_from_pdf_to_claim_cache() -> None:
    data = case("sample_case_a.json")
    report = Report.model_validate(data["report"])
    cache = VerifiedClaimCache.from_fixture_directory(FIXTURES)

    run = extract_document_page(
        run_id="extract-a-171",
        pdf_path=REFERENCES / "Samsung-Biologics-2025-ESG-Report_KR.pdf",
        report=report,
        page=171,
        mode=ExecutionMode.VERIFIED_CACHE,
        cache=cache,
        run_lock=RunLock(),
        clock=lambda: NOW,
    )

    assert run.state is RunState.COMPLETED
    assert run.result is not None
    assert run.result.claims[0].id == "claim-a-scope1"
    assert run.result.execution_mode is ExecutionMode.VERIFIED_CACHE
    assert [event.stage for event in run.trace] == [
        "문서 추출 계획",
        "PDF 페이지 추출",
        "주장 후보 필터",
        "Claim 구조화",
    ]
    assert all(event.created_at == NOW for event in run.trace)


def test_filter_counts_and_candidate_locations_are_traced() -> None:
    data = case("sample_case_b.json")
    report = Report.model_validate(data["report"])

    run = extract_document_page(
        run_id="extract-b-68",
        pdf_path=REFERENCES / "Samsung_Electronics_Sustainability_Report_2025_ENG.pdf",
        report=report,
        page=68,
        mode=ExecutionMode.VERIFIED_CACHE,
        cache=VerifiedClaimCache.from_fixture_directory(FIXTURES),
        run_lock=RunLock(),
        clock=lambda: NOW,
    )
    event = next(item for item in run.trace if item.stage == "주장 후보 필터")

    assert "included=" in event.input_summary
    assert "excluded=" in event.input_summary
    assert event.evidence
    assert all(location.startswith("page:68:line:") for location in event.evidence)


def test_table_context_restores_scope_header_to_domestic_value_row() -> None:
    data = case("sample_case_a.json")
    client = CapturingClient()

    run = extract_document_page(
        run_id="extract-a-171-table-context",
        pdf_path=REFERENCES / "Samsung-Biologics-2025-ESG-Report_KR.pdf",
        report=Report.model_validate(data["report"]),
        page=171,
        mode=ExecutionMode.LIVE,
        cache=VerifiedClaimCache(),
        client=client,
        table_context_label=(
            "Scope 1 온실가스 배출량 · 대한민국 국내 사업장 · "
            "2022·2023·2024 순"
        ),
        run_lock=RunLock(),
        clock=lambda: NOW,
    )

    assert run.state is RunState.COMPLETED
    restored = [
        text
        for text in client.candidate_texts
        if text.startswith("[표 문맥:") and "71,840.290" in text
    ]
    assert len(restored) == 1
    assert "Scope 1 온실가스 배출량" in restored[0]
    assert "국내 사업장" in restored[0]

    scope2_client = CapturingClient()
    scope2_run = extract_document_page(
        run_id="extract-a-172-table-context",
        pdf_path=REFERENCES / "Samsung-Biologics-2025-ESG-Report_KR.pdf",
        report=Report.model_validate(data["report"]),
        page=172,
        mode=ExecutionMode.LIVE,
        cache=VerifiedClaimCache(),
        client=scope2_client,
        table_context_label=(
            "Scope 2 온실가스 배출량 · 대한민국 국내 사업장 · "
            "2022·2023·2024 순"
        ),
        run_lock=RunLock(),
        clock=lambda: NOW,
    )
    assert scope2_run.state is RunState.COMPLETED
    assert any(
        "Scope 2 온실가스 배출량" in text
        and "배출권거래제 기준" in text
        and "154,678.989" in text
        for text in scope2_client.candidate_texts
    )

    total_client = CapturingClient()
    total_run = extract_document_page(
        run_id="extract-a-220-table-context",
        pdf_path=REFERENCES / "Samsung-Biologics-2025-ESG-Report_KR.pdf",
        report=Report.model_validate(data["report"]),
        page=220,
        mode=ExecutionMode.LIVE,
        cache=VerifiedClaimCache(),
        client=total_client,
        table_context_label=(
            "2024년 온실가스 검증보고서 · 추출 대상 Scope 1+2 총량 1건 · "
            "공시 주체 삼성바이오로직스 기업 · 조직경계 별도 · "
            "운영통제하 전체 배출원 · 단위 tCO2eq"
        ),
        table_context_row_marker="삼성바이오로직스 주식회사",
        table_context_require_unit=False,
        run_lock=RunLock(),
        clock=lambda: NOW,
    )
    assert total_run.state is RunState.COMPLETED
    assert any(
        "추출 대상 Scope 1+2 총량 1건" in text and "226,519" in text
        for text in total_client.candidate_texts
    )


def test_report_hash_mismatch_is_visible_failure() -> None:
    data = case("sample_case_a.json")
    report = Report.model_validate(
        {**data["report"], "file_hash": "sha256:" + "0" * 64}
    )

    run = extract_document_page(
        run_id="extract-hash-failure",
        pdf_path=REFERENCES / "Samsung-Biologics-2025-ESG-Report_KR.pdf",
        report=report,
        page=171,
        mode=ExecutionMode.VERIFIED_CACHE,
        cache=VerifiedClaimCache.from_fixture_directory(FIXTURES),
        run_lock=RunLock(),
        clock=lambda: NOW,
    )

    assert run.state is RunState.FAILED
    assert run.result is None
    assert "PDF 해시" in run.error
    assert run.trace[-1].stage == "문서 추출 실패"


def test_missing_pdf_is_visible_failure() -> None:
    data = case("sample_case_a.json")

    run = extract_document_page(
        run_id="extract-missing-file",
        pdf_path=REFERENCES / "missing.pdf",
        report=Report.model_validate(data["report"]),
        page=171,
        mode=ExecutionMode.VERIFIED_CACHE,
        cache=VerifiedClaimCache.from_fixture_directory(FIXTURES),
        run_lock=RunLock(),
        clock=lambda: NOW,
    )

    assert run.state is RunState.FAILED
    assert "FileNotFoundError" in run.error
    assert run.trace[-1].stage == "문서 추출 실패"
