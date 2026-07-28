"""백엔드·프론트·fixture가 함께 사용하는 대조 MVP 데이터 계약."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class ClaimType(StrEnum):
    REDUCTION_TARGET = "감축목표"
    PERFORMANCE = "실적주장"
    TRANSITION = "전환주장"
    CERTIFICATION = "인증주장"
    QUALITATIVE = "정성주장"


class AnalysisStatus(StrEnum):
    MATCH = "일치"
    EXPLAINED_DIFFERENCE = "설명된 차이"
    POSSIBLY_EXPLAINED = "설명 가능성 있음"
    UNEXPLAINED_DIFFERENCE = "설명되지 않은 차이"
    NOT_COMPARABLE = "비교 불가"
    INSUFFICIENT_INFORMATION = "정보 부족"


class MatchType(StrEnum):
    EXACT = "exact"
    PRECISION_COMPATIBLE = "precision_compatible"
    DIFFERENT = "different"


class Scope(StrEnum):
    SCOPE_1 = "Scope 1"
    SCOPE_2 = "Scope 2"
    SCOPE_1_2 = "Scope 1+2"
    SCOPE_1_2_3 = "Scope 1+2+3"


class Scope2Method(StrEnum):
    LOCATION_BASED = "지역기반"
    MARKET_BASED = "시장기반"
    ETS = "배출권거래제 기준"


class ValueBasis(StrEnum):
    ABSOLUTE = "절대량"
    INTENSITY = "원단위"


class EntityLevel(StrEnum):
    COMPANY = "기업"
    BUSINESS_SITE = "사업장"


class OrganizationBoundary(StrEnum):
    CONSOLIDATED = "연결"
    SEPARATE = "별도"
    BUSINESS_SITE = "개별 사업장"


class DisclosureDuty(StrEnum):
    MANDATORY = "의무"
    VOLUNTARY = "자율"
    UNKNOWN = "미확인"


class ConditionStatus(StrEnum):
    MATCH = "일치"
    MISMATCH = "불일치"
    MISSING = "누락"
    NOT_APPLICABLE = "해당 없음"


class ReviewAction(StrEnum):
    REQUEST_INFORMATION = "추가 자료 요청"
    COMPLETE = "검토 완료"
    HOLD = "보류"


class TraceStepType(StrEnum):
    PLAN = "계획"
    OBSERVATION = "관찰"
    ACTION = "행동"


class ExecutionMode(StrEnum):
    LIVE = "live"
    VERIFIED_CACHE = "verified_cache"
    FALLBACK = "fallback"


class Company(ContractModel):
    id: str
    legal_name: str
    identifiers: dict[str, str] = Field(default_factory=dict)
    aliases: list[str] = Field(default_factory=list)


class Report(ContractModel):
    id: str
    company_id: str
    title: str
    reporting_year: int
    file_hash: str
    source_url: str


class Claim(ContractModel):
    id: str
    report_id: str
    claim_type: ClaimType
    metric: str
    value: Decimal | None
    unit: str | None
    value_basis: ValueBasis | None
    period_start: str | None
    period_end: str | None
    baseline_year: int | None = None
    target_year: int | None = None
    scope: Scope | None
    scope2_method: Scope2Method | None
    organization_boundary: OrganizationBoundary | None
    geographic_boundary: str | None
    entity_level: EntityLevel | None
    raw_text: str
    page: int = Field(ge=1)
    evidence: str
    confidence: float = Field(ge=0, le=1)
    extraction_mode: ExecutionMode


class PublicFact(ContractModel):
    id: str
    company_id: str
    site_id: str | None = None
    entity_level: EntityLevel
    metric: str
    raw_value: Decimal | None
    normalized_value: Decimal | None
    unit: str | None
    value_basis: ValueBasis | None
    period_start: str | None
    period_end: str | None
    scope: Scope | None
    scope2_method: Scope2Method | None
    organization_boundary: OrganizationBoundary | None
    geographic_boundary: str | None
    display_decimal_places: int | None = Field(default=None, ge=0)
    display_rule: str | None = None
    disclosure_duty: DisclosureDuty
    source_url: str
    retrieved_at: datetime
    source_hash: str
    version: str

    @model_validator(mode="after")
    def preserve_value_pair(self) -> "PublicFact":
        if (self.raw_value is None) != (self.normalized_value is None):
            raise ValueError("raw_value와 normalized_value는 함께 존재하거나 함께 null이어야 합니다")
        return self


class ComparabilityCondition(ContractModel):
    field: str
    status: ConditionStatus
    claim_value: str | None = None
    public_value: str | None = None
    reason: str | None = None
    normalized_unit: str | None = None
    claim_unit_multiplier: Decimal | None = None
    public_unit_multiplier: Decimal | None = None


class ComparabilityResult(ContractModel):
    comparable: bool
    conditions: list[ComparabilityCondition]
    missing_fields: list[str] = Field(default_factory=list)
    mismatch_reasons: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def enforce_stop_reasons(self) -> "ComparabilityResult":
        has_problem = bool(self.missing_fields or self.mismatch_reasons)
        if self.comparable and has_problem:
            raise ValueError("비교 가능한 결과에는 누락 또는 불일치 사유가 있을 수 없습니다")
        if not self.comparable and not has_problem:
            raise ValueError("비교 불가 결과에는 누락 또는 불일치 사유가 필요합니다")
        return self


class Verdict(ContractModel):
    status: AnalysisStatus
    match_type: MatchType | None = None
    claim_raw_value: Decimal | None = None
    public_raw_value: Decimal | None = None
    claim_normalized_value: Decimal | None = None
    public_normalized_value: Decimal | None = None
    absolute_difference: Decimal | None = None
    relative_difference_pct: Decimal | None = None
    explanation: str
    review_required: bool
    review_reasons: list[str] = Field(default_factory=list)
    follow_up_question: str | None = None

    @model_validator(mode="after")
    def forbid_calculation_when_stopped(self) -> "Verdict":
        if self.status in {
            AnalysisStatus.NOT_COMPARABLE,
            AnalysisStatus.INSUFFICIENT_INFORMATION,
        } and any(
            value is not None
            for value in (
                self.absolute_difference,
                self.relative_difference_pct,
                self.claim_normalized_value,
                self.public_normalized_value,
            )
        ):
            raise ValueError("비교 불가 또는 정보 부족 상태에서는 비교 계산값을 저장할 수 없습니다")
        return self


class TargetProgress(ContractModel):
    readiness: str
    baseline_value: Decimal | None = None
    current_value: Decimal | None = None
    actual_reduction_pct: Decimal | None = None
    published_annual_path: list[dict[str, Decimal | int]] | None = None
    plan_gap: Decimal | None = None
    on_track: bool | None = None

    @model_validator(mode="after")
    def require_published_path_for_track_status(self) -> "TargetProgress":
        if self.on_track is not None and not self.published_annual_path:
            raise ValueError("공개된 연차 경로 없이 on_track을 생성할 수 없습니다")
        return self


class TraceEvent(ContractModel):
    step_type: TraceStepType
    stage: str
    tool_name: str | None = None
    input_summary: str
    evidence: list[str] = Field(default_factory=list)
    created_at: datetime


class HumanReview(ContractModel):
    case_id: str
    action: ReviewAction
    note: str
    reviewer: str
    processed_at: datetime
    previous_action: ReviewAction | None = None


class MonitoringCase(ContractModel):
    id: str
    company_id: str
    report_id: str
    case_type: str
    next_review_date: str
    importance: str
    synthetic: bool
