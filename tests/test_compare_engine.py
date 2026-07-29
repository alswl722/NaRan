import json
from decimal import Decimal
from pathlib import Path

import pytest

import db.compare_engine as compare_engine
from db.compare_engine import (
    DifferenceEvidence,
    calculate_target_progress,
    compare_performance,
)
from db.entity_map import DEFAULT_ENTITY_MAP, SourceSystem
from naran.contracts import AnalysisStatus, Claim, MatchType, PublicFact


FIXTURES = Path(__file__).parents[1] / "fixtures"
CASE_A_COMPANY_ID = "company-samsung-biologics"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def models(name: str, claim_index: int = 0, fact_index: int = 0):
    case = load(name)
    return (
        case,
        Claim.model_validate(case["claims"][claim_index]),
        PublicFact.model_validate(case["public_facts"][fact_index]),
    )


def case_a_mapping():
    mapping = DEFAULT_ENTITY_MAP.find(
        source_system=SourceSystem.ENV_INFO,
        source_entity_id="CT000000000000002772",
        company_id="company-samsung-biologics",
        year=2024,
    )
    assert mapping is not None
    return mapping


def test_exact_match_after_unit_normalization() -> None:
    _, claim, fact = models("sample_case_c.json")
    fact_data = fact.model_dump(mode="json")
    fact_data["raw_value"] = "100000"
    fact_data["normalized_value"] = "100000"

    outcome = compare_performance(claim, PublicFact.model_validate(fact_data))

    assert outcome.verdict.status is AnalysisStatus.MATCH
    assert outcome.verdict.match_type is MatchType.EXACT
    assert outcome.verdict.absolute_difference == 0


def test_case_a_scope1_is_precision_compatible() -> None:
    case, claim, fact = models("sample_case_a.json")

    outcome = compare_performance(
        claim,
        fact,
        boundary_mapping=case_a_mapping(),
        claim_company_id=CASE_A_COMPANY_ID,
    )

    assert outcome.verdict.status is AnalysisStatus.MATCH
    assert outcome.verdict.match_type is MatchType.PRECISION_COMPATIBLE
    assert outcome.verdict.review_required
    assert outcome.verdict.absolute_difference == Decimal("0.290")
    assert "표시 규칙은 미확인" in outcome.verdict.explanation
    assert outcome.verdict.model_dump(mode="json") == case["expected_verdict"]


def test_case_a_scope2_is_precision_compatible_at_integer_display() -> None:
    _, claim, fact = models("sample_case_a.json", claim_index=1, fact_index=1)

    outcome = compare_performance(
        claim,
        fact,
        boundary_mapping=case_a_mapping(),
        claim_company_id=CASE_A_COMPANY_ID,
    )

    assert outcome.verdict.status is AnalysisStatus.MATCH
    assert outcome.verdict.match_type is MatchType.PRECISION_COMPATIBLE
    assert outcome.verdict.review_required
    assert outcome.verdict.absolute_difference == Decimal("0.011")


def test_confirmed_rounding_boundary_is_applied() -> None:
    _, claim, fact = models("sample_case_a.json")
    claim_data = claim.model_dump(mode="json")
    fact_data = fact.model_dump(mode="json")
    claim_data["value"] = "71840.500"
    fact_data["raw_value"] = "71841"
    fact_data["normalized_value"] = "71841"
    fact_data["display_rule"] = "반올림"

    outcome = compare_performance(
        Claim.model_validate(claim_data),
        PublicFact.model_validate(fact_data),
        boundary_mapping=case_a_mapping(),
        claim_company_id=CASE_A_COMPANY_ID,
    )

    assert outcome.verdict.match_type is MatchType.PRECISION_COMPATIBLE
    assert "확인된 표시 규칙(반올림)" in outcome.verdict.explanation


def test_value_outside_precision_boundary_is_different() -> None:
    _, claim, fact = models("sample_case_a.json")
    claim_data = claim.model_dump(mode="json")
    fact_data = fact.model_dump(mode="json")
    claim_data["value"] = "71840.499"
    fact_data["raw_value"] = "71841"
    fact_data["normalized_value"] = "71841"
    fact_data["display_rule"] = "반올림"

    outcome = compare_performance(
        Claim.model_validate(claim_data),
        PublicFact.model_validate(fact_data),
        boundary_mapping=case_a_mapping(),
        claim_company_id=CASE_A_COMPANY_ID,
    )

    assert outcome.verdict.match_type is MatchType.DIFFERENT


def test_case_b_stops_without_any_calculation_values() -> None:
    case, claim, fact = models("sample_case_b.json")

    outcome = compare_performance(claim, fact)

    assert outcome.verdict.status is AnalysisStatus.NOT_COMPARABLE
    assert outcome.verdict.absolute_difference is None
    assert outcome.verdict.relative_difference_pct is None
    assert outcome.verdict.claim_normalized_value is None
    assert outcome.verdict.public_normalized_value is None
    assert outcome.verdict.model_dump(mode="json") == case["expected_verdict"]


def test_case_b_returns_before_normalization(monkeypatch) -> None:
    _, claim, fact = models("sample_case_b.json")

    def fail_if_called(_):
        raise AssertionError("비교 불가 입력에서 계산 준비가 호출됨")

    monkeypatch.setattr(compare_engine, "_unit_multipliers", fail_if_called)

    outcome = compare_performance(claim, fact)

    assert outcome.verdict.status is AnalysisStatus.NOT_COMPARABLE


def test_case_c_difference_and_question_match_fixture() -> None:
    case, claim, fact = models("sample_case_c.json")

    outcome = compare_performance(claim, fact)

    assert outcome.verdict.absolute_difference == Decimal("25000")
    assert outcome.verdict.relative_difference_pct == Decimal("25")
    assert outcome.verdict.model_dump(mode="json") == case["expected_verdict"]


def test_zero_claim_does_not_create_relative_difference() -> None:
    _, claim, fact = models("sample_case_c.json")
    claim_data = claim.model_dump(mode="json")
    claim_data["value"] = "0"

    outcome = compare_performance(Claim.model_validate(claim_data), fact)

    assert outcome.verdict.match_type is MatchType.DIFFERENT
    assert outcome.verdict.relative_difference_pct is None
    assert any("0이므로" in reason for reason in outcome.verdict.review_reasons)


def test_confirmed_difference_evidence_changes_status_without_llm_calculation() -> None:
    _, claim, fact = models("sample_case_c.json")

    outcome = compare_performance(
        claim,
        fact,
        difference_evidence=DifferenceEvidence.CONFIRMED,
        evidence_note="보고서에서 조직변동에 따른 재산정을 명시함",
        evidence_source="report-c-2024:p.1",
    )

    assert outcome.verdict.status is AnalysisStatus.EXPLAINED_DIFFERENCE
    assert not outcome.verdict.review_required
    assert outcome.verdict.follow_up_question is None
    assert "report-c-2024:p.1" in outcome.verdict.explanation


def test_confirmed_difference_requires_description_and_source() -> None:
    _, claim, fact = models("sample_case_c.json")

    with pytest.raises(ValueError, match="설명과 출처"):
        compare_performance(
            claim,
            fact,
            difference_evidence=DifferenceEvidence.CONFIRMED,
            evidence_note="조직변동",
        )


def test_evidence_metadata_is_rejected_when_evidence_is_none() -> None:
    _, claim, fact = models("sample_case_c.json")

    with pytest.raises(ValueError, match="지정할 수 없습니다"):
        compare_performance(claim, fact, evidence_note="근거 없는 설명")


def test_public_normalized_value_must_match_raw_value_and_unit() -> None:
    _, _, fact = models("sample_case_c.json")
    fact_data = fact.model_dump(mode="json")
    fact_data["normalized_value"] = "999"

    with pytest.raises(ValueError, match="단위 환산 결과"):
        PublicFact.model_validate(fact_data)


def test_unknown_display_rule_is_rejected() -> None:
    _, _, fact = models("sample_case_c.json")
    fact_data = fact.model_dump(mode="json")
    fact_data["display_rule"] = "대충 반올림"

    with pytest.raises(ValueError, match="display_rule"):
        PublicFact.model_validate(fact_data)


def test_noncomparable_input_stops_before_evidence_validation() -> None:
    _, claim, fact = models("sample_case_b.json")

    outcome = compare_performance(
        claim,
        fact,
        difference_evidence=DifferenceEvidence.CONFIRMED,
    )

    assert outcome.verdict.status is AnalysisStatus.NOT_COMPARABLE


def test_reduction_target_is_rejected_by_performance_engine() -> None:
    _, claim, fact = models("sample_case_c.json")
    claim_data = claim.model_dump(mode="json")
    claim_data["claim_type"] = "감축목표"

    with pytest.raises(ValueError, match="실적주장"):
        compare_performance(Claim.model_validate(claim_data), fact)


def test_target_without_published_path_does_not_invent_track_status() -> None:
    progress = calculate_target_progress(
        baseline_value=Decimal("100"),
        current_value=Decimal("80"),
    )

    assert progress.actual_reduction_pct == Decimal("20")
    assert progress.on_track is None
    assert progress.plan_gap is None


def test_zero_target_baseline_does_not_divide_by_zero() -> None:
    progress = calculate_target_progress(
        baseline_value=Decimal("0"),
        current_value=Decimal("0"),
    )

    assert progress.actual_reduction_pct is None
    assert progress.on_track is None


def test_published_path_allows_deterministic_track_status() -> None:
    progress = calculate_target_progress(
        baseline_value=Decimal("100"),
        current_value=Decimal("79"),
        published_annual_path=[
            {"year": 2024, "value": Decimal("80")},
            {"year": 2025, "value": Decimal("70")},
        ],
        current_year=2024,
    )

    assert progress.on_track is True
    assert progress.plan_gap == Decimal("-1")


def test_duplicate_year_in_published_path_is_rejected() -> None:
    with pytest.raises(ValueError, match="중복 연도"):
        calculate_target_progress(
            baseline_value=Decimal("100"),
            current_value=Decimal("80"),
            published_annual_path=[
                {"year": 2024, "value": Decimal("80")},
                {"year": 2024, "value": Decimal("70")},
            ],
            current_year=2024,
        )
