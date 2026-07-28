import json
from pathlib import Path

import pytest

from api.agent.llm_extract import VerifiedClaimCache
from api.agent.orchestrator import RunState
from api.agent.pipeline import analyze_verified_case
from naran.contracts import AnalysisStatus, Verdict


FIXTURES = Path(__file__).parents[1] / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def verified_cache() -> VerifiedClaimCache:
    return VerifiedClaimCache.from_fixture_directory(FIXTURES)


@pytest.mark.parametrize(
    "name",
    ["sample_case_a.json", "sample_case_b.json", "sample_case_c.json"],
)
def test_all_verified_cases_complete_through_same_pipeline(
    name: str,
    verified_cache: VerifiedClaimCache,
) -> None:
    analysis = analyze_verified_case(load(name), cache=verified_cache)

    assert analysis.runs
    assert all(run.state is RunState.COMPLETED for run in analysis.runs)
    assert all(
        extraction.execution_mode == "verified_cache"
        for extraction in analysis.extractions
    )


def test_case_a_runs_all_three_verified_claims(
    verified_cache: VerifiedClaimCache,
) -> None:
    analysis = analyze_verified_case(
        load("sample_case_a.json"),
        cache=verified_cache,
    )

    assert len(analysis.runs) == 3
    assert all(run.outcome is not None for run in analysis.runs)
    assert all(
        run.outcome.comparability.comparable
        for run in analysis.runs
        if run.outcome is not None
    )
    assert {
        run.outcome.verdict.match_type
        for run in analysis.runs
        if run.outcome is not None
    } == {"exact", "precision_compatible"}


def test_case_b_stops_without_calculation(
    verified_cache: VerifiedClaimCache,
) -> None:
    analysis = analyze_verified_case(
        load("sample_case_b.json"),
        cache=verified_cache,
    )
    run = analysis.runs[0]

    assert run.outcome is not None
    assert run.outcome.verdict.status is AnalysisStatus.NOT_COMPARABLE
    assert run.outcome.verdict.absolute_difference is None
    assert any(event.stage == "계산 중단" for event in run.trace)


def test_case_c_matches_expected_verdict(
    verified_cache: VerifiedClaimCache,
) -> None:
    case = load("sample_case_c.json")
    analysis = analyze_verified_case(case, cache=verified_cache)
    run = analysis.runs[0]

    assert run.outcome is not None
    assert run.outcome.verdict == Verdict.model_validate(case["expected_verdict"])


def test_pipeline_rejects_cross_company_case_data(
    verified_cache: VerifiedClaimCache,
) -> None:
    case = load("sample_case_c.json")
    case["report"]["company_id"] = "another-company"

    with pytest.raises(ValueError, match="Report와 Company"):
        analyze_verified_case(case, cache=verified_cache)


def test_pipeline_requires_matching_public_fact(
    verified_cache: VerifiedClaimCache,
) -> None:
    case = load("sample_case_c.json")
    case["public_facts"][0]["scope"] = "Scope 1"

    with pytest.raises(ValueError, match="대응하는 PublicFact"):
        analyze_verified_case(case, cache=verified_cache)


def test_pipeline_rejects_public_fact_from_another_company(
    verified_cache: VerifiedClaimCache,
) -> None:
    case = load("sample_case_c.json")
    case["public_facts"][0]["company_id"] = "another-company"

    with pytest.raises(ValueError, match="PublicFact와 Company"):
        analyze_verified_case(case, cache=verified_cache)


def test_pipeline_rejects_duplicate_public_fact_ids(
    verified_cache: VerifiedClaimCache,
) -> None:
    case = load("sample_case_c.json")
    case["public_facts"].append(dict(case["public_facts"][0]))

    with pytest.raises(ValueError, match="중복 ID"):
        analyze_verified_case(case, cache=verified_cache)
