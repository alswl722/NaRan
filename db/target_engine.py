"""감축목표의 기준정보를 검사하고 공개된 값만으로 진척도를 계산한다."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from db.compare_engine import calculate_target_progress
from naran.contracts import Claim, ClaimType, PublicFact, Scope, TargetProgress


@dataclass(frozen=True)
class TargetOutcome:
    progress: TargetProgress
    missing_fields: tuple[str, ...]
    mismatch_reasons: tuple[str, ...]

    @property
    def trackable(self) -> bool:
        return not self.missing_fields and not self.mismatch_reasons


def _year(fact: PublicFact) -> int | None:
    return int(fact.period_start[:4]) if fact.period_start else None


def evaluate_target_progress(
    claim: Claim,
    baseline_fact: PublicFact,
    current_fact: PublicFact,
    *,
    claim_company_id: str,
    published_annual_path: list[dict[str, Decimal | int]] | None = None,
) -> TargetOutcome:
    """목표와 두 공개 사실의 조건이 맞을 때만 감축률을 계산한다."""

    if claim.claim_type is not ClaimType.REDUCTION_TARGET:
        raise ValueError("감축목표만 evaluate_target_progress로 평가할 수 있습니다")

    missing: list[str] = []
    mismatches: list[str] = []
    if claim.baseline_year is None:
        missing.append("baseline_year")
    if claim.target_year is None:
        missing.append("target_year")
    if claim.value is None:
        missing.append("target_reduction_pct")
    if baseline_fact.normalized_value is None:
        missing.append("baseline_value")
    if current_fact.normalized_value is None:
        missing.append("current_value")
    if baseline_fact.period_start is None:
        missing.append("baseline_period")
    if current_fact.period_start is None:
        missing.append("current_period")
    if claim.unit != "%":
        mismatches.append("감축목표 단위는 %여야 함")
    if claim.value is not None and (
        not claim.value.is_finite()
        or not Decimal("0") <= claim.value <= Decimal("100")
    ):
        mismatches.append("감축목표율은 0~100% 범위여야 함")
    if (
        claim.target_year is not None
        and claim.baseline_year is not None
        and claim.target_year <= claim.baseline_year
    ):
        mismatches.append("목표연도는 기준연도보다 늦어야 함")
    if baseline_fact.company_id != claim_company_id:
        mismatches.append("기준연도 데이터의 회사가 다름")
    if current_fact.company_id != claim_company_id:
        mismatches.append("현재 데이터의 회사가 다름")
    baseline_year = _year(baseline_fact)
    current_year = _year(current_fact)
    if (
        claim.baseline_year is not None
        and baseline_year is not None
        and baseline_year != claim.baseline_year
    ):
        mismatches.append("기준연도 데이터의 기간이 다름")
    if (
        current_year is not None
        and claim.target_year is not None
        and current_year > claim.target_year
    ):
        mismatches.append("현재 데이터가 목표연도 이후임")
    if (
        current_year is not None
        and claim.baseline_year is not None
        and current_year < claim.baseline_year
    ):
        mismatches.append("현재 데이터가 기준연도보다 이전임")
    if baseline_fact.normalized_value is not None and (
        not baseline_fact.normalized_value.is_finite()
        or baseline_fact.normalized_value <= 0
    ):
        mismatches.append("기준값은 유한한 0보다 큰 값이어야 함")
    if current_fact.normalized_value is not None and (
        not current_fact.normalized_value.is_finite()
        or current_fact.normalized_value < 0
    ):
        mismatches.append("현재값은 유한한 0 이상의 값이어야 함")

    comparable_fields = [
        ("metric", claim.metric, baseline_fact.metric, current_fact.metric),
        ("scope", claim.scope, baseline_fact.scope, current_fact.scope),
        (
            "value_basis",
            claim.value_basis,
            baseline_fact.value_basis,
            current_fact.value_basis,
        ),
        (
            "organization_boundary",
            claim.organization_boundary,
            baseline_fact.organization_boundary,
            current_fact.organization_boundary,
        ),
        (
            "geographic_boundary",
            claim.geographic_boundary,
            baseline_fact.geographic_boundary,
            current_fact.geographic_boundary,
        ),
        (
            "entity_level",
            claim.entity_level,
            baseline_fact.entity_level,
            current_fact.entity_level,
        ),
    ]
    if claim.scope in {Scope.SCOPE_2, Scope.SCOPE_1_2, Scope.SCOPE_1_2_3}:
        comparable_fields.append(
            (
                "scope2_method",
                claim.scope2_method,
                baseline_fact.scope2_method,
                current_fact.scope2_method,
            )
        )
    for field, claim_value, baseline_value, current_value in comparable_fields:
        if (
            claim_value is None
            or baseline_value is None
            or current_value is None
        ):
            missing.append(field)
        elif not (claim_value == baseline_value == current_value):
            mismatches.append(f"{field} 조건이 다름")
    normalized_units = {"tCO2eq", "1000 tCO2eq"}
    units_compatible = baseline_fact.unit == current_fact.unit or (
        baseline_fact.unit in normalized_units
        and current_fact.unit in normalized_units
    )
    if not units_compatible:
        mismatches.append("기준연도와 현재 데이터의 단위가 다름")
    if (
        published_annual_path
        and claim.baseline_year is not None
        and claim.target_year is not None
    ):
        for point in published_annual_path:
            year = point.get("year")
            if (
                isinstance(year, int)
                and not isinstance(year, bool)
                and not claim.baseline_year <= year <= claim.target_year
            ):
                mismatches.append("연차 경로가 기준연도·목표연도 범위를 벗어남")

    if mismatches or missing:
        readiness = (
            "목표 추적 조건 불일치" if mismatches else "목표 추적 정보 부족"
        )
        return TargetOutcome(
            progress=TargetProgress(readiness=readiness),
            missing_fields=tuple(dict.fromkeys(missing)),
            mismatch_reasons=tuple(dict.fromkeys(mismatches)),
        )

    baseline_value = baseline_fact.normalized_value
    current_value = current_fact.normalized_value
    if baseline_value is None or current_value is None:
        raise RuntimeError("목표 계산 전 값 검증 상태가 일관되지 않습니다")
    progress = calculate_target_progress(
        baseline_value=baseline_value,
        current_value=current_value,
        published_annual_path=published_annual_path,
        current_year=current_year,
    )
    return TargetOutcome(
        progress=progress,
        missing_fields=(),
        mismatch_reasons=(),
    )
