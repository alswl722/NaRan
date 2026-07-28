"""비교 가능한 값만 계산하는 결정론적 대조 엔진."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from enum import StrEnum

from db.comparability import check_comparability, stop_status
from db.entity_map import EntityMapping
from naran.contracts import (
    AnalysisStatus,
    Claim,
    ClaimType,
    ComparabilityResult,
    ConditionStatus,
    MatchType,
    PublicFact,
    TargetProgress,
    Verdict,
)


class DifferenceEvidence(StrEnum):
    NONE = "none"
    POSSIBLE = "possible"
    CONFIRMED = "confirmed"


@dataclass(frozen=True)
class ComparisonOutcome:
    comparability: ComparabilityResult
    verdict: Verdict


def _unit_multipliers(result: ComparabilityResult) -> tuple[Decimal, Decimal]:
    unit = next(condition for condition in result.conditions if condition.field == "unit")
    if unit.claim_unit_multiplier is None or unit.public_unit_multiplier is None:
        raise ValueError("비교 가능한 결과에 단위 환산 정보가 없습니다")
    return unit.claim_unit_multiplier, unit.public_unit_multiplier


def _decimal_quantum(value: Decimal) -> Decimal:
    return Decimal(1).scaleb(value.as_tuple().exponent)


def _display_quantum(
    claim: Claim,
    public_fact: PublicFact,
    claim_multiplier: Decimal,
    public_multiplier: Decimal,
) -> Decimal:
    claim_quantum = _decimal_quantum(claim.value) * claim_multiplier
    public_places = public_fact.display_decimal_places
    public_quantum = (
        Decimal(1).scaleb(-public_places) * public_multiplier
        if public_places is not None
        else _decimal_quantum(public_fact.raw_value) * public_multiplier
    )
    return max(claim_quantum, public_quantum)


def _project(value: Decimal, quantum: Decimal, rule: str) -> Decimal:
    rounding = ROUND_HALF_UP if rule == "round_half_up" else ROUND_DOWN
    return (value / quantum).to_integral_value(rounding=rounding) * quantum


def _precision_compatible(
    claim_value: Decimal,
    public_value: Decimal,
    quantum: Decimal,
    display_rule: str | None,
) -> tuple[bool, str]:
    aliases = {
        "반올림": "round_half_up",
        "round_half_up": "round_half_up",
        "절사": "truncate",
        "truncate": "truncate",
    }
    confirmed_rule = aliases.get(display_rule or "")
    rules = (confirmed_rule,) if confirmed_rule else ("round_half_up", "truncate")
    compatible = any(
        _project(claim_value, quantum, rule) == _project(public_value, quantum, rule)
        for rule in rules
    )
    if confirmed_rule:
        return compatible, f"확인된 표시 규칙({display_rule})과 표시 정밀도 기준"
    return compatible, "표시 정밀도 범위 내 정합; 출처의 표시 규칙은 미확인"


def _format_decimal(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    whole, dot, fraction = text.partition(".")
    formatted = f"{int(whole):,}"
    return f"{formatted}.{fraction}" if dot else formatted


def _difference_verdict(
    *,
    claim: Claim,
    claim_raw: Decimal,
    public_raw: Decimal,
    claim_normalized: Decimal,
    public_normalized: Decimal,
    normalized_unit: str,
    evidence: DifferenceEvidence,
    evidence_note: str | None,
) -> Verdict:
    difference = abs(public_normalized - claim_normalized)
    relative = (
        (difference / abs(claim_normalized) * Decimal("100")).normalize()
        if claim_normalized != 0
        else None
    )
    if evidence is DifferenceEvidence.CONFIRMED:
        status = AnalysisStatus.EXPLAINED_DIFFERENCE
        review_required = False
        explanation = evidence_note or "문서에서 차이 원인이 확인됨"
        review_reasons: list[str] = []
    elif evidence is DifferenceEvidence.POSSIBLE:
        status = AnalysisStatus.POSSIBLY_EXPLAINED
        review_required = True
        explanation = evidence_note or "차이 원인 후보가 있으나 근거 확인이 필요함"
        review_reasons = ["차이 원인 근거 확인 필요"]
    else:
        status = AnalysisStatus.UNEXPLAINED_DIFFERENCE
        review_required = True
        explanation = "동일한 비교 조건에서 차이가 발생했으며 공개된 설명 근거가 없음"
        review_reasons = ["동일 범위 수치 간 설명되지 않은 차이"]

    relative_note = (
        f"주장값 대비 {_format_decimal(relative)}%"
        if relative is not None
        else "주장값이 0이므로 상대 차이율은 계산하지 않음"
    )
    geographic = (
        "국내 사업장"
        if claim.geographic_boundary == "대한민국 국내 사업장"
        else claim.geographic_boundary
    )
    question = (
        f"동일한 {claim.period_start[:4]}년 {geographic} "
        f"{claim.scope} 배출량 간 {_format_decimal(difference)}{normalized_unit} "
        f"차이가 발생한 "
        f"원인과 산정 근거를 제출해 주세요."
    )
    if relative is None:
        review_reasons.append(relative_note)

    return Verdict(
        status=status,
        match_type=MatchType.DIFFERENT,
        claim_raw_value=claim_raw,
        public_raw_value=public_raw,
        claim_normalized_value=claim_normalized,
        public_normalized_value=public_normalized,
        absolute_difference=difference,
        relative_difference_pct=relative,
        explanation=explanation,
        review_required=review_required,
        review_reasons=review_reasons,
        follow_up_question=question if review_required else None,
    )


def compare_performance(
    claim: Claim,
    public_fact: PublicFact,
    *,
    boundary_mapping: EntityMapping | None = None,
    difference_evidence: DifferenceEvidence = DifferenceEvidence.NONE,
    evidence_note: str | None = None,
) -> ComparisonOutcome:
    if claim.claim_type is not ClaimType.PERFORMANCE:
        raise ValueError("실적주장만 compare_performance로 대조할 수 있습니다")
    comparability = check_comparability(
        claim,
        public_fact,
        boundary_mapping=boundary_mapping,
    )
    if not comparability.comparable:
        status = stop_status(comparability)
        assert status is not None
        mismatch_fields = {
            condition.field
            for condition in comparability.conditions
            if condition.status is ConditionStatus.MISMATCH
        }
        boundary_mismatch = bool(
            {"entity_level", "organization_boundary", "geographic_boundary"}
            & mismatch_fields
        )
        if status is AnalysisStatus.NOT_COMPARABLE and boundary_mismatch:
            explanation = "조직 및 지역 범위가 달라 계산을 중단함"
            reasons = [
                reason
                for field, reason in (
                    ("organization_boundary", "조직경계 불일치"),
                    ("geographic_boundary", "지역경계 불일치"),
                )
                if field in mismatch_fields
            ]
            follow_up = "동일한 조직·지역 범위의 배출량 자료를 제출해 주세요."
        elif status is AnalysisStatus.NOT_COMPARABLE:
            explanation = "비교 조건이 달라 계산을 중단함"
            reasons = comparability.mismatch_reasons
            follow_up = "동일한 비교 조건의 자료를 제출해 주세요."
        else:
            explanation = "비교에 필요한 정보가 부족하여 계산을 중단함"
            reasons = comparability.missing_fields
            follow_up = "누락된 비교 정보와 산정 근거를 제출해 주세요."
        verdict = Verdict(
            status=status,
            explanation=explanation,
            review_required=True,
            review_reasons=list(reasons),
            follow_up_question=follow_up,
        )
        return ComparisonOutcome(comparability=comparability, verdict=verdict)

    claim_multiplier, public_multiplier = _unit_multipliers(comparability)
    normalized_unit = next(
        condition.normalized_unit
        for condition in comparability.conditions
        if condition.field == "unit"
    )
    if normalized_unit is None:
        raise ValueError("비교 가능한 결과에 정규화 단위가 없습니다")
    assert claim.value is not None
    assert public_fact.raw_value is not None
    claim_normalized = claim.value * claim_multiplier
    public_normalized = public_fact.raw_value * public_multiplier
    difference = abs(public_normalized - claim_normalized)

    if claim_normalized == public_normalized:
        verdict = Verdict(
            status=AnalysisStatus.MATCH,
            match_type=MatchType.EXACT,
            claim_raw_value=claim.value,
            public_raw_value=public_fact.raw_value,
            claim_normalized_value=claim_normalized,
            public_normalized_value=public_normalized,
            absolute_difference=Decimal("0"),
            relative_difference_pct=Decimal("0"),
            explanation="원본값을 공통단위로 정규화한 결과 완전 일치",
            review_required=False,
        )
        return ComparisonOutcome(comparability=comparability, verdict=verdict)

    quantum = _display_quantum(
        claim, public_fact, claim_multiplier, public_multiplier
    )
    compatible, precision_explanation = _precision_compatible(
        claim_normalized,
        public_normalized,
        quantum,
        public_fact.display_rule,
    )
    if compatible:
        verdict = Verdict(
            status=AnalysisStatus.MATCH,
            match_type=MatchType.PRECISION_COMPATIBLE,
            claim_raw_value=claim.value,
            public_raw_value=public_fact.raw_value,
            claim_normalized_value=claim_normalized,
            public_normalized_value=public_normalized,
            absolute_difference=difference,
            relative_difference_pct=None,
            explanation=precision_explanation,
            review_required=False,
        )
        return ComparisonOutcome(comparability=comparability, verdict=verdict)

    verdict = _difference_verdict(
        claim=claim,
        claim_raw=claim.value,
        public_raw=public_fact.raw_value,
        claim_normalized=claim_normalized,
        public_normalized=public_normalized,
        normalized_unit=normalized_unit,
        evidence=difference_evidence,
        evidence_note=evidence_note,
    )
    return ComparisonOutcome(comparability=comparability, verdict=verdict)


def calculate_target_progress(
    *,
    baseline_value: Decimal | None,
    current_value: Decimal | None,
    published_annual_path: list[dict[str, Decimal | int]] | None = None,
    current_year: int | None = None,
) -> TargetProgress:
    if baseline_value is None or current_value is None:
        return TargetProgress(readiness="기준값 또는 현재값 부족")
    if baseline_value == 0:
        return TargetProgress(
            readiness="기준값이 0이어서 감축률 계산 불가",
            baseline_value=baseline_value,
            current_value=current_value,
        )

    actual_reduction = (
        (baseline_value - current_value) / abs(baseline_value) * Decimal("100")
    )
    if not published_annual_path:
        return TargetProgress(
            readiness="연차 경로 없음",
            baseline_value=baseline_value,
            current_value=current_value,
            actual_reduction_pct=actual_reduction,
        )

    year_target = next(
        (
            Decimal(str(point["value"]))
            for point in published_annual_path
            if current_year is not None and point.get("year") == current_year
        ),
        None,
    )
    if year_target is None:
        return TargetProgress(
            readiness="현재연도 경로 없음",
            baseline_value=baseline_value,
            current_value=current_value,
            actual_reduction_pct=actual_reduction,
            published_annual_path=published_annual_path,
        )
    plan_gap = current_value - year_target
    return TargetProgress(
        readiness="추적 가능",
        baseline_value=baseline_value,
        current_value=current_value,
        actual_reduction_pct=actual_reduction,
        published_annual_path=published_annual_path,
        plan_gap=plan_gap,
        on_track=current_value <= year_target,
    )
