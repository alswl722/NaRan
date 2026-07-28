import json
from decimal import Decimal
from pathlib import Path

from api.agent.orchestrator import (
    RunLock,
    RunState,
    analyze_reduction_target,
)
from db.target_engine import evaluate_target_progress
from naran.contracts import Claim, PublicFact, Report


FIXTURES = Path(__file__).parents[1] / "fixtures"


def target_models():
    case = json.loads(
        (FIXTURES / "sample_case_c.json").read_text(encoding="utf-8")
    )
    claim_data = dict(case["claims"][0])
    claim_data.update(
        {
            "id": "claim-target-c",
            "claim_type": "감축목표",
            "value": "30",
            "unit": "%",
            "baseline_year": 2020,
            "target_year": 2030,
            "raw_text": "2030년까지 2020년 대비 온실가스 배출량을 30% 감축합니다.",
        }
    )
    fact_data = dict(case["public_facts"][0])
    fact_data.update(
        {
            "id": "fact-current-c",
            "raw_value": "80",
            "normalized_value": "80",
        }
    )
    baseline_data = dict(fact_data)
    baseline_data.update(
        {
            "id": "fact-baseline-c",
            "raw_value": "100",
            "normalized_value": "100",
            "period_start": "2020-01-01",
            "period_end": "2020-12-31",
            "version": "fixture-2020",
        }
    )
    return (
        Report.model_validate(case["report"]),
        Claim.model_validate(claim_data),
        PublicFact.model_validate(baseline_data),
        PublicFact.model_validate(fact_data),
    )


def test_target_without_published_path_calculates_reduction_only() -> None:
    report, claim, baseline, current = target_models()

    outcome = evaluate_target_progress(
        claim,
        baseline,
        current,
        claim_company_id=report.company_id,
    )

    assert outcome.trackable
    assert outcome.progress.actual_reduction_pct == Decimal("20")
    assert outcome.progress.on_track is None
    assert outcome.progress.plan_gap is None
    assert outcome.progress.readiness == "연차 경로 없음"


def test_published_path_allows_on_track_calculation() -> None:
    report, claim, baseline, current = target_models()

    outcome = evaluate_target_progress(
        claim,
        baseline,
        current,
        claim_company_id=report.company_id,
        published_annual_path=[
            {"year": 2024, "value": Decimal("82")},
            {"year": 2030, "value": Decimal("70")},
        ],
    )

    assert outcome.progress.on_track is True
    assert outcome.progress.plan_gap == Decimal("-2")


def test_missing_baseline_value_stops_without_calculation() -> None:
    report, claim, baseline, current = target_models()
    baseline = baseline.model_copy(
        update={"raw_value": None, "normalized_value": None}
    )

    outcome = evaluate_target_progress(
        claim,
        baseline,
        current,
        claim_company_id=report.company_id,
    )

    assert not outcome.trackable
    assert "baseline_value" in outcome.missing_fields
    assert outcome.progress.actual_reduction_pct is None


def test_boundary_mismatch_stops_target_calculation() -> None:
    report, claim, baseline, current = target_models()
    current = current.model_copy(update={"geographic_boundary": "글로벌"})

    outcome = evaluate_target_progress(
        claim,
        baseline,
        current,
        claim_company_id=report.company_id,
    )

    assert not outcome.trackable
    assert "geographic_boundary 조건이 다름" in outcome.mismatch_reasons
    assert outcome.progress.actual_reduction_pct is None


def test_wrong_company_stops_target_calculation() -> None:
    report, claim, baseline, current = target_models()
    current = current.model_copy(update={"company_id": "another-company"})

    outcome = evaluate_target_progress(
        claim,
        baseline,
        current,
        claim_company_id=report.company_id,
    )

    assert "현재 데이터의 회사가 다름" in outcome.mismatch_reasons
    assert outcome.progress.actual_reduction_pct is None


def test_target_rate_outside_percentage_range_is_rejected() -> None:
    report, claim, baseline, current = target_models()
    claim = claim.model_copy(update={"value": Decimal("101")})

    outcome = evaluate_target_progress(
        claim,
        baseline,
        current,
        claim_company_id=report.company_id,
    )

    assert "감축목표율은 0~100% 범위여야 함" in outcome.mismatch_reasons


def test_target_orchestrator_records_no_invented_path_status() -> None:
    report, claim, baseline, current = target_models()

    run = analyze_reduction_target(
        run_id="run-target-c",
        report=report,
        claim=claim,
        baseline_fact=baseline,
        current_fact=current,
        run_lock=RunLock(),
    )

    assert run.state is RunState.COMPLETED
    assert run.outcome is not None
    assert run.outcome.progress.on_track is None
    assert [event.stage for event in run.trace] == [
        "목표 추적 계획",
        "감축목표 추출 결과",
        "목표 추적 조건 검사",
        "감축률 계산",
    ]


def test_target_orchestrator_records_explicit_stop() -> None:
    report, claim, baseline, current = target_models()
    current = current.model_copy(update={"scope": "Scope 1"})

    run = analyze_reduction_target(
        run_id="run-target-stop",
        report=report,
        claim=claim,
        baseline_fact=baseline,
        current_fact=current,
        run_lock=RunLock(),
    )

    assert run.state is RunState.COMPLETED
    assert run.outcome is not None
    assert run.trace[-1].stage == "목표 계산 중단"


def test_scope1_target_does_not_require_scope2_method() -> None:
    report, claim, baseline, current = target_models()
    claim = claim.model_copy(update={"scope": "Scope 1", "scope2_method": None})
    baseline = baseline.model_copy(update={"scope": "Scope 1", "scope2_method": None})
    current = current.model_copy(update={"scope": "Scope 1", "scope2_method": None})

    outcome = evaluate_target_progress(
        claim,
        baseline,
        current,
        claim_company_id=report.company_id,
    )

    assert outcome.trackable
    assert "scope2_method" not in outcome.missing_fields


def test_value_basis_mismatch_stops_target_calculation() -> None:
    report, claim, baseline, current = target_models()
    current = current.model_copy(update={"value_basis": "원단위"})

    outcome = evaluate_target_progress(
        claim,
        baseline,
        current,
        claim_company_id=report.company_id,
    )

    assert "value_basis 조건이 다름" in outcome.mismatch_reasons
    assert outcome.progress.actual_reduction_pct is None


def test_current_data_before_baseline_year_is_rejected() -> None:
    report, claim, baseline, current = target_models()
    current = current.model_copy(
        update={
            "period_start": "2019-01-01",
            "period_end": "2019-12-31",
        }
    )

    outcome = evaluate_target_progress(
        claim,
        baseline,
        current,
        claim_company_id=report.company_id,
    )

    assert "현재 데이터가 기준연도보다 이전임" in outcome.mismatch_reasons


def test_target_orchestrator_rejects_claim_from_another_report() -> None:
    report, claim, baseline, current = target_models()
    claim = claim.model_copy(update={"report_id": "another-report"})

    run = analyze_reduction_target(
        run_id="run-target-wrong-report",
        report=report,
        claim=claim,
        baseline_fact=baseline,
        current_fact=current,
        run_lock=RunLock(),
    )

    assert run.state is RunState.FAILED
    assert run.trace[-1].stage == "목표 분석 실패"
