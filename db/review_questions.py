"""비교 결과를 담당자의 추가자료 요청 문구로 변환한다."""

from __future__ import annotations

from decimal import Decimal

from naran.contracts import (
    Claim,
    ComparabilityResult,
    ConditionStatus,
)


FIELD_LABELS = {
    "value": "수치",
    "metric": "지표",
    "unit": "단위",
    "value_basis": "절대량·원단위 기준",
    "entity_level": "기업·사업장 단위",
    "organization_boundary": "조직경계",
    "geographic_boundary": "지역경계",
    "scope": "Scope 범위",
    "scope2_method": "Scope 2 산정 방식",
    "period": "보고기간",
}


def _format_decimal(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    whole, dot, fraction = text.partition(".")
    formatted = f"{int(whole):,}"
    return f"{formatted}.{fraction}" if dot else formatted


def question_for_stopped_comparison(
    claim: Claim,
    result: ComparabilityResult,
) -> str:
    """누락과 불일치 조건을 자료 요청 질문으로 바꾼다."""

    mismatch_labels = [
        FIELD_LABELS.get(condition.field, condition.field)
        for condition in result.conditions
        if condition.status is ConditionStatus.MISMATCH
    ]
    missing_labels = [
        FIELD_LABELS.get(field, field) for field in result.missing_fields
    ]
    requests: list[str] = []
    if mismatch_labels:
        requests.append(
            f"동일한 {'·'.join(mismatch_labels)} 조건의 "
            f"{claim.metric} 자료를 제출해 주세요."
        )
    if missing_labels:
        requests.append(
            f"비교에 필요한 {'·'.join(missing_labels)} 정보와 "
            "산정 근거를 제출해 주세요."
        )
    if not requests:
        raise ValueError("비교가 중단된 결과에 누락 또는 불일치 조건이 없습니다")
    return " ".join(requests)


def question_for_numeric_difference(
    claim: Claim,
    *,
    absolute_difference: Decimal,
    normalized_unit: str,
) -> str:
    """같은 비교 조건에서 발생한 수치 차이에 대한 질문을 만든다."""

    if not absolute_difference.is_finite() or absolute_difference < 0:
        raise ValueError("절대 차이는 유한한 0 이상의 값이어야 합니다")
    if not normalized_unit.strip():
        raise ValueError("차이 질문 생성에 정규화 단위가 필요합니다")
    if not claim.period_start or not claim.geographic_boundary or not claim.scope:
        raise ValueError("차이 질문 생성에 기간·지역경계·Scope가 필요합니다")
    geographic = (
        "국내 사업장"
        if claim.geographic_boundary == "대한민국 국내 사업장"
        else claim.geographic_boundary
    )
    return (
        f"동일한 {claim.period_start[:4]}년 {geographic} "
        f"{claim.scope} {claim.metric} 간 "
        f"{_format_decimal(absolute_difference)}{normalized_unit} "
        "차이가 발생한 원인과 산정 근거를 제출해 주세요."
    )
