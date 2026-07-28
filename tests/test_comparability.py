import json
from copy import deepcopy
from pathlib import Path

import pytest

from db.comparability import check_comparability
from db.entity_map import DEFAULT_ENTITY_MAP
from naran.contracts import Claim, ConditionStatus, PublicFact


FIXTURES = Path(__file__).parents[1] / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def result_for(claim_data: dict, fact_data: dict, **kwargs):
    return check_comparability(
        Claim.model_validate(claim_data),
        PublicFact.model_validate(fact_data),
        **kwargs,
    )


def test_case_a_is_fully_comparable() -> None:
    case = load("sample_case_a.json")
    result = result_for(case["claims"][0], case["public_facts"][0])

    assert result.comparable
    assert result.missing_fields == []
    assert result.mismatch_reasons == []


def test_case_b_stops_for_known_boundary_mismatches() -> None:
    case = load("sample_case_b.json")
    result = result_for(case["claims"][0], case["public_facts"][0])
    statuses = {condition.field: condition.status for condition in result.conditions}

    assert not result.comparable
    assert statuses["entity_level"] is ConditionStatus.MISMATCH
    assert statuses["organization_boundary"] is ConditionStatus.MISMATCH
    assert statuses["geographic_boundary"] is ConditionStatus.MISMATCH
    assert "scope2_method" in result.missing_fields


def test_explicit_mapping_can_align_differently_labelled_boundary() -> None:
    case = load("sample_case_a.json")
    fact = deepcopy(case["public_facts"][0])
    fact["entity_level"] = "사업장"
    fact["organization_boundary"] = "개별 사업장"
    fact["geographic_boundary"] = "대한민국"
    aligned = DEFAULT_ENTITY_MAP.permits_boundary_alignment(
        source_system="env-info",
        source_entity_id=fact["site_id"],
        company_id=fact["company_id"],
        year=2024,
    )

    result = result_for(
        case["claims"][0],
        fact,
        boundary_alignment_verified=aligned,
    )

    assert result.comparable


@pytest.mark.parametrize(
    ("field", "replacement", "reason"),
    [
        ("organization_boundary", "연결", "조직경계가 다름"),
        ("geographic_boundary", "글로벌", "지역경계가 다름"),
        ("scope", "Scope 2", "Scope 범위가 다름"),
        ("period_end", "2023-12-31", "보고기간이 다름"),
        ("value_basis", "원단위", "절대량과 원단위 기준이 다름"),
    ],
)
def test_mismatched_condition_stops_comparison(
    field: str, replacement: str, reason: str
) -> None:
    case = load("sample_case_a.json")
    fact = deepcopy(case["public_facts"][0])
    fact[field] = replacement

    result = result_for(case["claims"][0], fact)

    assert not result.comparable
    assert reason in result.mismatch_reasons


def test_scope2_method_mismatch_stops_comparison() -> None:
    case = load("sample_case_a.json")
    fact = deepcopy(case["public_facts"][1])
    fact["scope2_method"] = "시장기반"

    result = result_for(case["claims"][1], fact)

    assert not result.comparable
    assert "Scope 2 산정 방식이 다름" in result.mismatch_reasons


def test_missing_required_metadata_is_recorded() -> None:
    case = load("sample_case_a.json")
    fact = deepcopy(case["public_facts"][1])
    fact["scope2_method"] = None

    result = result_for(case["claims"][1], fact)

    assert not result.comparable
    assert "scope2_method" in result.missing_fields


def test_compatible_tonne_units_are_not_a_mismatch() -> None:
    case = load("sample_case_b.json")
    result = result_for(case["claims"][0], case["public_facts"][0])
    unit_condition = next(
        condition for condition in result.conditions if condition.field == "unit"
    )

    assert unit_condition.status is ConditionStatus.MATCH
