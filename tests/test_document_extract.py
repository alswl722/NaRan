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
