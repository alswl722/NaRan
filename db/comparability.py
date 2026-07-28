"""주장과 공개 데이터가 계산 가능한 범위인지 검사하는 순수 함수."""

from __future__ import annotations

from decimal import Decimal

from naran.contracts import (
    AnalysisStatus,
    Claim,
    ComparabilityCondition,
    ComparabilityResult,
    ConditionStatus,
    PublicFact,
    Scope,
)

from db.entity_map import EntityMapping, SourceSystem


_UNIT_SCALE_TO_TCO2EQ = {
    "tCO2eq": Decimal("1"),
    "1000 tCO2eq": Decimal("1000"),
}


def _text(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value)


def _condition(
    field: str,
    claim_value: object | None,
    public_value: object | None,
    *,
    required: bool = True,
    equivalent: bool | None = None,
    mismatch_reason: str,
) -> ComparabilityCondition:
    if not required:
        return ComparabilityCondition(
            field=field,
            status=ConditionStatus.NOT_APPLICABLE,
            claim_value=_text(claim_value),
            public_value=_text(public_value),
            reason=None,
        )
    if claim_value is None or public_value is None:
        return ComparabilityCondition(
            field=field,
            status=ConditionStatus.MISSING,
            claim_value=_text(claim_value),
            public_value=_text(public_value),
            reason=f"{field} 비교에 필요한 값이 누락됨",
        )
    is_equal = equivalent if equivalent is not None else claim_value == public_value
    return ComparabilityCondition(
        field=field,
        status=ConditionStatus.MATCH if is_equal else ConditionStatus.MISMATCH,
        claim_value=_text(claim_value),
        public_value=_text(public_value),
        reason=None if is_equal else mismatch_reason,
    )


def _units_compatible(claim_unit: str | None, public_unit: str | None) -> bool:
    if claim_unit is None or public_unit is None:
        return False
    return claim_unit == public_unit or (
        claim_unit in _UNIT_SCALE_TO_TCO2EQ
        and public_unit in _UNIT_SCALE_TO_TCO2EQ
    )


def _source_system_for(public_fact: PublicFact) -> SourceSystem | None:
    if "env-info.kr/" in public_fact.source_url:
        return SourceSystem.ENV_INFO
    if "gir.go.kr/" in public_fact.source_url:
        return SourceSystem.GIR
    return None


def _reporting_year(claim: Claim, public_fact: PublicFact) -> int | None:
    starts = (claim.period_start, public_fact.period_start)
    if any(value is None or len(value) < 4 for value in starts):
        return None
    years = {int(value[:4]) for value in starts if value is not None}
    return years.pop() if len(years) == 1 else None


def _mapping_permits_alignment(
    mapping: EntityMapping | None,
    claim: Claim,
    public_fact: PublicFact,
) -> bool:
    year = _reporting_year(claim, public_fact)
    source_system = _source_system_for(public_fact)
    return bool(
        mapping is not None
        and year is not None
        and source_system is not None
        and mapping.source_system is source_system
        and mapping.source_entity_id == public_fact.site_id
        and mapping.company_id == public_fact.company_id
        and mapping.permits_boundary_alignment(year)
    )


def _value_presence_condition(
    claim: Claim, public_fact: PublicFact
) -> ComparabilityCondition:
    if claim.value is None or public_fact.raw_value is None:
        return ComparabilityCondition(
            field="value",
            status=ConditionStatus.MISSING,
            claim_value=_text(claim.value),
            public_value=_text(public_fact.raw_value),
            reason="수치 비교에 필요한 값이 누락됨",
        )
    return ComparabilityCondition(
        field="value",
        status=ConditionStatus.MATCH,
        claim_value=_text(claim.value),
        public_value=_text(public_fact.raw_value),
        reason="양쪽 수치 존재 확인; 값의 차이는 대조 엔진에서 계산",
    )


def _unit_condition(claim: Claim, public_fact: PublicFact) -> ComparabilityCondition:
    condition = _condition(
        "unit",
        claim.unit,
        public_fact.unit,
        equivalent=_units_compatible(claim.unit, public_fact.unit),
        mismatch_reason="단위가 호환되지 않음",
    )
    if condition.status is ConditionStatus.MATCH:
        convertible_tonnes = (
            claim.unit in _UNIT_SCALE_TO_TCO2EQ
            and public_fact.unit in _UNIT_SCALE_TO_TCO2EQ
        )
        condition.normalized_unit = "tCO2eq" if convertible_tonnes else claim.unit
        condition.claim_unit_multiplier = (
            _UNIT_SCALE_TO_TCO2EQ[claim.unit] if convertible_tonnes else Decimal("1")
        )
        condition.public_unit_multiplier = (
            _UNIT_SCALE_TO_TCO2EQ[public_fact.unit]
            if convertible_tonnes
            else Decimal("1")
        )
        if claim.unit != public_fact.unit:
            condition.reason = "공통단위 tCO2eq로 환산 가능"
    return condition


def check_comparability(
    claim: Claim,
    public_fact: PublicFact,
    *,
    boundary_mapping: EntityMapping | None = None,
) -> ComparabilityResult:
    """조건별 결과를 반환하며 수치 차이는 계산하지 않는다."""

    includes_scope2 = claim.scope in {Scope.SCOPE_2, Scope.SCOPE_1_2, Scope.SCOPE_1_2_3}
    same_period = (
        claim.period_start == public_fact.period_start
        and claim.period_end == public_fact.period_end
    )
    boundary_alignment_verified = _mapping_permits_alignment(
        boundary_mapping, claim, public_fact
    )

    conditions = [
        _value_presence_condition(claim, public_fact),
        _condition(
            "metric",
            claim.metric,
            public_fact.metric,
            mismatch_reason="지표가 다름",
        ),
        _unit_condition(claim, public_fact),
        _condition(
            "value_basis",
            claim.value_basis,
            public_fact.value_basis,
            mismatch_reason="절대량과 원단위 기준이 다름",
        ),
        _condition(
            "entity_level",
            claim.entity_level,
            public_fact.entity_level,
            equivalent=boundary_alignment_verified
            or claim.entity_level == public_fact.entity_level,
            mismatch_reason="기업과 사업장 단위가 다름",
        ),
        _condition(
            "organization_boundary",
            claim.organization_boundary,
            public_fact.organization_boundary,
            equivalent=boundary_alignment_verified
            or claim.organization_boundary == public_fact.organization_boundary,
            mismatch_reason="조직경계가 다름",
        ),
        _condition(
            "geographic_boundary",
            claim.geographic_boundary,
            public_fact.geographic_boundary,
            equivalent=boundary_alignment_verified
            or claim.geographic_boundary == public_fact.geographic_boundary,
            mismatch_reason="지역경계가 다름",
        ),
        _condition(
            "scope",
            claim.scope,
            public_fact.scope,
            mismatch_reason="Scope 범위가 다름",
        ),
        _condition(
            "scope2_method",
            claim.scope2_method,
            public_fact.scope2_method,
            required=includes_scope2,
            mismatch_reason="Scope 2 산정 방식이 다름",
        ),
        _condition(
            "period",
            f"{claim.period_start}/{claim.period_end}"
            if claim.period_start and claim.period_end
            else None,
            f"{public_fact.period_start}/{public_fact.period_end}"
            if public_fact.period_start and public_fact.period_end
            else None,
            equivalent=same_period,
            mismatch_reason="보고기간이 다름",
        ),
    ]

    missing_fields = [
        condition.field
        for condition in conditions
        if condition.status is ConditionStatus.MISSING
    ]
    mismatch_reasons = [
        condition.reason
        for condition in conditions
        if condition.status is ConditionStatus.MISMATCH and condition.reason
    ]
    return ComparabilityResult(
        comparable=not missing_fields and not mismatch_reasons,
        conditions=conditions,
        missing_fields=missing_fields,
        mismatch_reasons=mismatch_reasons,
    )


def stop_status(result: ComparabilityResult) -> AnalysisStatus | None:
    """확정된 불일치를 누락보다 우선해 분석 중단 상태를 결정한다."""
    if result.comparable:
        return None
    if result.mismatch_reasons:
        return AnalysisStatus.NOT_COMPARABLE
    return AnalysisStatus.INSUFFICIENT_INFORMATION
