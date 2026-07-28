"""문서에서 찾은 차이 원인 근거를 제한된 규칙으로 평가한다.

LLM은 후보를 구조화할 수 있지만 최종 분석 상태는 만들지 않는다. 이 모듈은
원문 위치와 차이 연결성이 확인된 후보만 대조 엔진의 근거 수준으로 변환한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pydantic import Field, model_validator

from db.compare_engine import DifferenceEvidence
from naran.contracts import ContractModel


class DifferenceCause(StrEnum):
    ORGANIZATION_CHANGE = "조직변동"
    BASELINE_RECALCULATION = "기준연도 재산정"
    METHODOLOGY_CHANGE = "산정 방식 변경"
    BOUNDARY_CHANGE = "조직·지역 범위 변경"
    DISCLOSURE_TIMING = "공시 시점 차이"


class EvidenceSupport(StrEnum):
    CANDIDATE = "candidate"
    EXPLICIT = "explicit"


class DifferenceFinding(ContractModel):
    cause: DifferenceCause
    support: EvidenceSupport
    explanation: str = Field(min_length=1)
    raw_text: str = Field(min_length=1)
    page: int = Field(ge=1)
    source_ref: str = Field(min_length=1)
    mentions_cause: bool
    mentions_affected_period_or_value: bool

    @model_validator(mode="after")
    def explicit_support_requires_linked_text(self) -> "DifferenceFinding":
        if any(
            not value.strip()
            for value in (self.explanation, self.raw_text, self.source_ref)
        ):
            raise ValueError("근거 설명·원문·출처는 공백일 수 없습니다")
        if self.support is EvidenceSupport.EXPLICIT and not (
            self.mentions_cause and self.mentions_affected_period_or_value
        ):
            raise ValueError(
                "explicit 근거는 원인과 영향받는 기간 또는 수치를 함께 명시해야 합니다"
            )
        if not self.mentions_cause:
            raise ValueError("차이 원인 후보는 원인을 명시한 원문이 필요합니다")
        return self


@dataclass(frozen=True)
class DifferenceAssessment:
    evidence: DifferenceEvidence
    note: str | None
    source: str | None
    findings: tuple[DifferenceFinding, ...]


def assess_difference_findings(
    findings: list[DifferenceFinding],
) -> DifferenceAssessment:
    """검증된 후보를 대조 엔진이 받는 단일 근거 수준으로 축약한다."""

    if not findings:
        return DifferenceAssessment(
            evidence=DifferenceEvidence.NONE,
            note=None,
            source=None,
            findings=(),
        )

    explicit = [
        finding
        for finding in findings
        if finding.support is EvidenceSupport.EXPLICIT
        and finding.mentions_cause
        and finding.mentions_affected_period_or_value
    ]
    selected = explicit if explicit else findings
    evidence = (
        DifferenceEvidence.CONFIRMED
        if explicit
        else DifferenceEvidence.POSSIBLE
    )
    ordered = sorted(
        selected,
        key=lambda finding: (finding.source_ref, finding.page, finding.cause.value),
    )
    note = "; ".join(
        f"{finding.cause}: {finding.explanation}" for finding in ordered
    )
    source = "; ".join(
        f"{finding.source_ref}#page={finding.page}" for finding in ordered
    )
    return DifferenceAssessment(
        evidence=evidence,
        note=note,
        source=source,
        findings=tuple(ordered),
    )
