import json
from copy import deepcopy
from pathlib import Path

import pytest

from db.comparability import check_comparability, stop_status
from db.entity_map import (
    BoundaryCoverage,
    DEFAULT_ENTITY_MAP,
    EntityMapping,
    MappingStatus,
    SourceSystem,
)
from naran.contracts import (
    AnalysisStatus,
    Claim,
    ComparabilityResult,
    ConditionStatus,
    PublicFact,
)


FIXTURES = Path(__file__).parents[1] / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def result_for(claim_data: dict, fact_data: dict, **kwargs):
    return check_comparability(
        Claim.model_validate(claim_data),
        PublicFact.model_validate(fact_data),
        **kwargs,
    )


def case_a_mapping() -> EntityMapping:
    mapping = DEFAULT_ENTITY_MAP.find(
        source_system=SourceSystem.ENV_INFO,
        source_entity_id="CT000000000000002772",
        company_id="company-samsung-biologics",
        year=2024,
    )
    assert mapping is not None
    return mapping


def test_case_a_is_fully_comparable() -> None:
    case = load("sample_case_a.json")
    result = result_for(
        case["claims"][0],
        case["public_facts"][0],
        boundary_mapping=case_a_mapping(),
    )

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
    result = result_for(
        case["claims"][0],
        case["public_facts"][0],
        boundary_mapping=case_a_mapping(),
    )

    assert result.comparable


def test_unrelated_mapping_cannot_bypass_boundary_checks() -> None:
    case = load("sample_case_a.json")
    unrelated = EntityMapping(
        source_system=SourceSystem.ENV_INFO,
        source_entity_id="another-site",
        company_id="company-samsung-biologics",
        source_entity_name="다른 사업장",
        status=MappingStatus.VERIFIED,
        boundary_coverage=BoundaryCoverage.EXACT,
        valid_from_year=2024,
        valid_to_year=2024,
        evidence=("명시적 근거",),
        note="테스트",
    )

    result = result_for(
        case["claims"][0],
        case["public_facts"][0],
        boundary_mapping=unrelated,
    )

    assert not result.comparable
    assert "기업과 사업장 단위가 다름" in result.mismatch_reasons


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


@pytest.mark.parametrize(("side", "field"), [("claim", "value"), ("fact", "raw_value")])
def test_missing_numeric_value_stops_comparison(side: str, field: str) -> None:
    case = load("sample_case_a.json")
    claim = deepcopy(case["claims"][0])
    fact = deepcopy(case["public_facts"][0])
    if side == "claim":
        claim[field] = None
    else:
        fact["raw_value"] = None
        fact["normalized_value"] = None

    result = result_for(claim, fact, boundary_mapping=case_a_mapping())

    assert not result.comparable
    assert "value" in result.missing_fields
    assert stop_status(result) is AnalysisStatus.INSUFFICIENT_INFORMATION


def test_confirmed_mismatch_has_priority_over_missing_metadata() -> None:
    case = load("sample_case_b.json")
    result = result_for(case["claims"][0], case["public_facts"][0])

    assert result.mismatch_reasons
    assert result.missing_fields
    assert stop_status(result) is AnalysisStatus.NOT_COMPARABLE


def test_compatible_tonne_units_are_not_a_mismatch() -> None:
    case = load("sample_case_b.json")
    result = result_for(case["claims"][0], case["public_facts"][0])
    unit_condition = next(
        condition for condition in result.conditions if condition.field == "unit"
    )

    assert unit_condition.status is ConditionStatus.MATCH
    assert unit_condition.normalized_unit == "tCO2eq"
    assert unit_condition.claim_unit_multiplier == 1000
    assert unit_condition.public_unit_multiplier == 1


@pytest.mark.parametrize(
    "name",
    ["sample_case_a.json", "sample_case_b.json", "sample_case_c.json"],
)
def test_fixture_comparability_summary_matches_engine(name: str) -> None:
    case = load(name)
    kwargs = {"boundary_mapping": case_a_mapping()} if name.endswith("_a.json") else {}
    result = result_for(case["claims"][0], case["public_facts"][0], **kwargs)
    expected = ComparabilityResult.model_validate(case["comparability"])

    assert result == expected
