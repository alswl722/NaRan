import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

from db.comparability import check_comparability
from db.review_questions import (
    question_for_numeric_difference,
    question_for_stopped_comparison,
)
from naran.contracts import Claim, PublicFact


FIXTURES = Path(__file__).parents[1] / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def models(name: str):
    case = load(name)
    return (
        case,
        Claim.model_validate(case["claims"][0]),
        PublicFact.model_validate(case["public_facts"][0]),
    )


def test_case_b_requests_same_organization_and_geographic_boundary() -> None:
    _, claim, fact = models("sample_case_b.json")
    result = check_comparability(claim, fact)

    assert (
        question_for_stopped_comparison(result)
        == "동일한 조직·지역 범위의 배출량 자료를 제출해 주세요."
    )


def test_missing_metadata_question_names_missing_fields() -> None:
    case = load("sample_case_c.json")
    fact_data = deepcopy(case["public_facts"][0])
    fact_data["scope2_method"] = None
    claim = Claim.model_validate(case["claims"][0])
    fact = PublicFact.model_validate(fact_data)
    result = check_comparability(claim, fact)

    question = question_for_stopped_comparison(result)

    assert "Scope 2 산정 방식" in question
    assert "산정 근거" in question


def test_nonboundary_mismatch_question_names_conditions() -> None:
    case = load("sample_case_c.json")
    fact_data = deepcopy(case["public_facts"][0])
    fact_data["scope"] = "Scope 2"
    claim = Claim.model_validate(case["claims"][0])
    fact = PublicFact.model_validate(fact_data)
    result = check_comparability(claim, fact)

    assert (
        question_for_stopped_comparison(result)
        == "동일한 Scope 범위 조건의 자료를 제출해 주세요."
    )


def test_case_c_difference_question_matches_ground_truth() -> None:
    _, claim, _ = models("sample_case_c.json")

    question = question_for_numeric_difference(
        claim,
        absolute_difference=Decimal("25000"),
        normalized_unit="tCO2eq",
    )

    assert question == (
        "동일한 2024년 국내 사업장 Scope 1+2 배출량 간 "
        "25,000tCO2eq 차이가 발생한 원인과 산정 근거를 제출해 주세요."
    )
