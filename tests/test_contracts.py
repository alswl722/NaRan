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
    assert all(claim["organization_boundary"] == "별도" for claim in case["claims"])


def test_case_b_verified_global_report_boundary() -> None:
    case = load("sample_case_b.json")
    claim = case["claims"][0]

    assert case["report"]["file_hash"].startswith("sha256:")
    assert claim["value"] == "14889"
    assert claim["unit"] == "1000 tCO2eq"
    assert claim["scope2_method"] == "시장기반"
    assert claim["geographic_boundary"] == "한국 및 해외 제조 자회사"
    assert case["comparability"]["comparable"] is False


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
