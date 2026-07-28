import pytest
from pydantic import ValidationError

from api.agent.review_difference import (
    DifferenceCause,
    DifferenceFinding,
    EvidenceSupport,
    assess_difference_findings,
)
from db.compare_engine import DifferenceEvidence, compare_performance
from naran.contracts import Claim, PublicFact

from tests.test_compare_engine import models


def finding(**overrides) -> DifferenceFinding:
    data = {
        "cause": DifferenceCause.BASELINE_RECALCULATION,
        "support": EvidenceSupport.EXPLICIT,
        "explanation": "2024년 조직변동을 반영해 기준연도 배출량을 재산정함",
        "raw_text": "조직변동을 반영하여 2024년 기준연도 배출량을 재산정하였다.",
        "page": 42,
        "source_ref": "report://company-c-2024",
        "mentions_cause": True,
        "mentions_affected_period_or_value": True,
    }
    data.update(overrides)
    return DifferenceFinding.model_validate(data)


def test_no_findings_produces_no_evidence() -> None:
    assessment = assess_difference_findings([])

    assert assessment.evidence is DifferenceEvidence.NONE
    assert assessment.note is None
    assert assessment.source is None


def test_candidate_finding_cannot_confirm_difference() -> None:
    assessment = assess_difference_findings(
        [
            finding(
                support=EvidenceSupport.CANDIDATE,
                mentions_affected_period_or_value=False,
            )
        ]
    )

    assert assessment.evidence is DifferenceEvidence.POSSIBLE
    assert assessment.note is not None
    assert assessment.source == "report://company-c-2024#page=42"


def test_text_without_cause_cannot_be_registered_as_candidate() -> None:
    with pytest.raises(ValidationError, match="원인을 명시한 원문"):
        finding(
            support=EvidenceSupport.CANDIDATE,
            mentions_cause=False,
            mentions_affected_period_or_value=False,
        )


def test_whitespace_only_evidence_is_rejected() -> None:
    with pytest.raises(ValidationError, match="공백일 수 없습니다"):
        finding(raw_text="   ")


@pytest.mark.parametrize(
    ("mentions_cause", "mentions_affected_period_or_value"),
    [(False, True), (True, False), (False, False)],
)
def test_explicit_finding_requires_cause_and_affected_value_link(
    mentions_cause: bool,
    mentions_affected_period_or_value: bool,
) -> None:
    with pytest.raises(ValidationError, match="원인과 영향받는"):
        finding(
            mentions_cause=mentions_cause,
            mentions_affected_period_or_value=mentions_affected_period_or_value,
        )


def test_explicit_finding_confirms_difference_with_traceable_source() -> None:
    assessment = assess_difference_findings([finding()])

    assert assessment.evidence is DifferenceEvidence.CONFIRMED
    assert "기준연도 재산정" in assessment.note
    assert assessment.source == "report://company-c-2024#page=42"


def test_assessment_can_feed_engine_without_llm_verdict() -> None:
    _, claim, fact = models("sample_case_c.json")
    assessment = assess_difference_findings([finding()])

    outcome = compare_performance(
        claim,
        fact,
        difference_evidence=assessment.evidence,
        evidence_note=assessment.note,
        evidence_source=assessment.source,
    )

    assert outcome.verdict.status == "설명된 차이"
    assert not outcome.verdict.review_required


def test_multiple_findings_have_deterministic_order() -> None:
    later = finding(
        cause=DifferenceCause.METHODOLOGY_CHANGE,
        page=50,
        explanation="산정 방식 변경",
    )
    earlier = finding(page=10, explanation="기준연도 재산정")

    first = assess_difference_findings([later, earlier])
    second = assess_difference_findings([earlier, later])

    assert first.note == second.note
    assert first.source == second.source
