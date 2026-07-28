import json
from datetime import datetime
from pathlib import Path

import pytest

from api.agent.review_difference import DifferenceFinding
from api.agent.orchestrator import (
    AnalysisRun,
    RunAlreadyActiveError,
    RunLock,
    RunState,
    analyze_performance,
)
from db.entity_map import DEFAULT_ENTITY_MAP, SourceSystem
from naran.contracts import Claim, ExecutionMode, PublicFact, Report


FIXTURES = Path(__file__).parents[1] / "fixtures"
NOW = datetime.fromisoformat("2026-07-28T12:00:00+09:00")


def load_case(name: str):
    case = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return (
        case,
        Report.model_validate(case["report"]),
        Claim.model_validate(case["claims"][0]),
        PublicFact.model_validate(case["public_facts"][0]),
    )


def run_case(name: str) -> AnalysisRun:
    _, report, claim, fact = load_case(name)
    mapping = None
    if name == "sample_case_a.json":
        mapping = DEFAULT_ENTITY_MAP.find(
            source_system=SourceSystem.ENV_INFO,
            source_entity_id=fact.site_id,
            company_id=fact.company_id,
            year=2024,
        )
        assert mapping is not None
    return analyze_performance(
        run_id=f"run-{name}",
        report=report,
        claim=claim,
        public_fact=fact,
        boundary_mapping=mapping,
        run_lock=RunLock(),
        clock=lambda: NOW,
    )


@pytest.mark.parametrize(
    "name",
    ["sample_case_a.json", "sample_case_b.json", "sample_case_c.json"],
)
def test_all_cases_use_same_completed_flow(name: str) -> None:
    run = run_case(name)

    assert run.state is RunState.COMPLETED
    assert run.outcome is not None
    assert run.trace[0].stage == "분석 계획"
    assert run.trace[-1].stage == "HITL 라우팅"
    assert all(event.created_at == NOW for event in run.trace)


def test_trace_preserves_report_and_public_data_provenance() -> None:
    case, _, _, _ = load_case("sample_case_a.json")
    run = run_case("sample_case_a.json")
    evidence = [item for event in run.trace for item in event.evidence]

    assert case["report"]["file_hash"] in evidence
    assert case["public_facts"][0]["source_url"] in evidence
    assert case["public_facts"][0]["source_hash"] in evidence
    assert case["public_facts"][0]["version"] in " ".join(
        event.input_summary for event in run.trace
    )


def test_case_b_records_explicit_calculation_stop() -> None:
    run = run_case("sample_case_b.json")
    stages = [event.stage for event in run.trace]

    assert "계산 중단" in stages
    assert "수치 대조" not in stages
    assert run.outcome is not None
    assert run.outcome.verdict.absolute_difference is None


def test_case_c_records_difference_review_and_hitl() -> None:
    run = run_case("sample_case_c.json")
    stages = [event.stage for event in run.trace]

    assert "수치 대조" in stages
    assert "차이 원인 재검토" in stages
    assert run.trace[-1].input_summary == "담당자 검토 대기열로 전달"


def test_orchestrator_assesses_structured_difference_evidence() -> None:
    _, report, claim, fact = load_case("sample_case_c.json")
    evidence = DifferenceFinding.model_validate(
        {
            "cause": "기준연도 재산정",
            "support": "explicit",
            "explanation": "2024년 배출량을 재산정함",
            "raw_text": "조직변동으로 2024년 배출량을 재산정하였다.",
            "page": 7,
            "source_ref": report.source_url,
            "mentions_cause": True,
            "mentions_affected_period_or_value": True,
        }
    )

    run = analyze_performance(
        run_id="run-confirmed-difference",
        report=report,
        claim=claim,
        public_fact=fact,
        difference_findings=[evidence],
        run_lock=RunLock(),
        clock=lambda: NOW,
    )

    assert run.state is RunState.COMPLETED
    assert run.outcome is not None
    assert run.outcome.verdict.status == "설명된 차이"
    review = next(event for event in run.trace if event.stage == "차이 원인 재검토")
    assert "confirmed" in review.input_summary


def test_failure_is_visible_in_state_and_trace() -> None:
    _, report, claim, fact = load_case("sample_case_c.json")
    claim_data = claim.model_copy(update={"claim_type": "감축목표"})

    run = analyze_performance(
        run_id="run-failure",
        report=report,
        claim=claim_data,
        public_fact=fact,
        run_lock=RunLock(),
        clock=lambda: NOW,
    )

    assert run.state is RunState.FAILED
    assert run.outcome is None
    assert run.error is not None
    assert run.trace[-1].stage == "분석 실패"


def test_fallback_mode_preserves_failure_reason_in_trace() -> None:
    _, report, claim, fact = load_case("sample_case_c.json")

    run = analyze_performance(
        run_id="run-fallback",
        report=report,
        claim=claim,
        public_fact=fact,
        public_data_mode=ExecutionMode.FALLBACK,
        fallback_reason="env-info 요청 시간 초과",
        run_lock=RunLock(),
        clock=lambda: NOW,
    )
    lookup = next(event for event in run.trace if event.stage == "공개 데이터 조회")

    assert run.state is RunState.COMPLETED
    assert "fallback" in lookup.input_summary
    assert "env-info 요청 시간 초과" in lookup.evidence


def test_fallback_without_failure_reason_is_failed_run() -> None:
    _, report, claim, fact = load_case("sample_case_c.json")

    run = analyze_performance(
        run_id="run-invalid-fallback",
        report=report,
        claim=claim,
        public_fact=fact,
        public_data_mode=ExecutionMode.FALLBACK,
        run_lock=RunLock(),
        clock=lambda: NOW,
    )

    assert run.state is RunState.FAILED
    assert run.trace[-1].stage == "분석 실패"


def test_run_lock_rejects_duplicate_active_run() -> None:
    lock = RunLock()
    lock.acquire("same-run")

    with pytest.raises(RunAlreadyActiveError):
        lock.acquire("same-run")

    lock.release("same-run")
    lock.acquire("same-run")
    lock.release("same-run")
