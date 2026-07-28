import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from naran.contracts import (
    Claim,
    Company,
    ComparabilityResult,
    MonitoringCase,
    PublicFact,
    Report,
    TargetProgress,
    TraceEvent,
    Verdict,
)


FIXTURES = Path(__file__).parents[1] / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", ["sample_case_a.json", "sample_case_b.json", "sample_case_c.json"])
def test_case_fixture_contracts(name: str) -> None:
    case = load(name)
    Company.model_validate(case["company"])
    ComparabilityResult.model_validate(case["comparability"])
    Verdict.model_validate(case["expected_verdict"])
    MonitoringCase.model_validate(case["monitoring_case"])


@pytest.mark.parametrize("name", ["sample_case_a.json", "sample_case_b.json", "sample_case_c.json"])
def test_case_full_report_claim_and_public_fact_contracts(name: str) -> None:
    case = load(name)
    Report.model_validate(case["report"])
    for claim in case["claims"]:
        Claim.model_validate(claim)
    for fact in case["public_facts"]:
        PublicFact.model_validate(fact)


def test_standalone_contract_samples() -> None:
    Claim.model_validate(load("sample_claim.json"))
    PublicFact.model_validate(load("sample_public_fact.json"))
    TraceEvent.model_validate(load("sample_trace.json"))


def test_case_a_verified_report_evidence() -> None:
    case = load("sample_case_a.json")
    claims = {claim["scope"]: claim for claim in case["claims"]}

    assert case["report"]["file_hash"].startswith("sha256:")
    assert claims["Scope 1"]["value"] == "71840.290"
    assert claims["Scope 1"]["page"] == 171
    assert claims["Scope 2"]["value"] == "154678.989"
    assert claims["Scope 2"]["scope2_method"] == "배출권거래제 기준"
    assert claims["Scope 2"]["page"] == 172
    assert claims["Scope 1+2"]["value"] == "226519"
    assert claims["Scope 1+2"]["page"] == 220
    assert all(claim["organization_boundary"] == "별도" for claim in case["claims"])


def test_case_a_verified_public_sources() -> None:
    case = load("sample_case_a.json")
    facts = {fact["id"]: fact for fact in case["public_facts"]}

    env_scope1 = facts["fact-a-scope1-envinfo"]
    env_scope2 = facts["fact-a-scope2-envinfo"]
    gir_total = facts["fact-a-scope1-2-gir"]

    assert env_scope1["raw_value"] == "71840"
    assert env_scope2["raw_value"] == "154679"
    assert env_scope1["source_hash"].startswith("sha256:")
    assert env_scope2["source_hash"] == env_scope1["source_hash"]
    assert gir_total["raw_value"] == "226519"
    assert gir_total["disclosure_duty"] == "의무"
    assert gir_total["source_hash"].startswith("sha256:")


def test_case_b_verified_global_report_boundary() -> None:
    case = load("sample_case_b.json")
    claim = case["claims"][0]

    assert case["report"]["file_hash"].startswith("sha256:")
    assert claim["value"] == "14889"
    assert claim["unit"] == "1000 tCO2eq"
    assert claim["scope2_method"] == "시장기반"
    assert claim["geographic_boundary"] == "한국 및 해외 제조 자회사"
    assert case["comparability"]["comparable"] is False

    public_fact = case["public_facts"][0]
    assert public_fact["site_id"] == "00000000000000095329"
    assert public_fact["raw_value"] == "192012"
    assert public_fact["scope2_method"] is None
    assert public_fact["source_hash"].startswith("sha256:")


def test_not_comparable_verdict_cannot_contain_calculation() -> None:
    verdict = load("sample_case_b.json")["expected_verdict"]
    verdict["absolute_difference"] = "1"
    with pytest.raises(ValidationError):
        Verdict.model_validate(verdict)


def test_noncomparable_result_requires_stop_reason() -> None:
    with pytest.raises(ValidationError):
        ComparabilityResult.model_validate(
            {
                "comparable": False,
                "conditions": [],
                "missing_fields": [],
                "mismatch_reasons": [],
            }
        )


def test_target_progress_cannot_invent_annual_path() -> None:
    with pytest.raises(ValidationError):
        TargetProgress.model_validate(
            {
                "readiness": "연차 경로 없음",
                "on_track": True,
            }
        )


def test_target_progress_cannot_store_plan_gap_without_path() -> None:
    with pytest.raises(ValidationError, match="연차 경로 없이"):
        TargetProgress.model_validate(
            {
                "readiness": "잘못된 결과",
                "plan_gap": "1",
            }
        )


def test_match_status_requires_match_type() -> None:
    with pytest.raises(ValidationError, match="exact 또는"):
        Verdict.model_validate(
            {
                "status": "일치",
                "explanation": "유형이 누락된 잘못된 결과",
                "review_required": False,
            }
        )


def test_review_required_verdict_requires_follow_up_question() -> None:
    verdict = load("sample_case_c.json")["expected_verdict"]
    verdict["follow_up_question"] = None

    with pytest.raises(ValidationError, match="후속 확인 질문"):
        Verdict.model_validate(verdict)


def test_comparability_summary_must_match_conditions() -> None:
    result = load("sample_case_b.json")["comparability"]
    result["missing_fields"] = []

    with pytest.raises(ValidationError, match="missing_fields"):
        ComparabilityResult.model_validate(result)


def test_public_fact_retrieval_time_requires_timezone() -> None:
    fact = load("sample_case_b.json")["public_facts"][0]
    fact["retrieved_at"] = "2026-07-28T00:00:00"

    with pytest.raises(ValidationError, match="시간대"):
        PublicFact.model_validate(fact)
