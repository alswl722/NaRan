"""api.agent.pipeline.CaseAnalysis 결과를 DB 레코드로 저장한다.

판정 로직은 만들지 않는다 — orchestrator/compare_engine이 이미 계산한
AnalysisRun·ComparisonOutcome을 그대로 옮겨 적을 뿐이다.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from api.agent.pipeline import CaseAnalysis
from db.models import (
    AnalysisRunRecord,
    Claim as ClaimRecord,
    ComparabilityResultRecord,
    TraceEventRecord,
    VerdictRecord,
)


def _persist_claims(session: Session, case_analysis: CaseAnalysis) -> None:
    """live 추출 Claim을 판정·트레이스와 같은 트랜잭션에 저장한다."""

    for extraction in case_analysis.extractions:
        for claim in extraction.claims:
            existing = session.get(ClaimRecord, claim.id)
            if existing is not None:
                continue
            session.add(
                ClaimRecord(
                    id=claim.id,
                    report_id=claim.report_id,
                    claim_type=claim.claim_type.value,
                    metric=claim.metric,
                    value=claim.value,
                    unit=claim.unit,
                    value_basis=(
                        claim.value_basis.value if claim.value_basis else None
                    ),
                    period_start=claim.period_start,
                    period_end=claim.period_end,
                    baseline_year=claim.baseline_year,
                    target_year=claim.target_year,
                    scope=claim.scope.value if claim.scope else None,
                    scope2_method=(
                        claim.scope2_method.value if claim.scope2_method else None
                    ),
                    organization_boundary=(
                        claim.organization_boundary.value
                        if claim.organization_boundary
                        else None
                    ),
                    geographic_boundary=claim.geographic_boundary,
                    entity_level=(
                        claim.entity_level.value if claim.entity_level else None
                    ),
                    raw_text=claim.raw_text,
                    page=claim.page,
                    evidence=claim.evidence,
                    confidence=claim.confidence,
                    extraction_mode=claim.extraction_mode.value,
                )
            )


def _decimal_str(value) -> str | None:
    return str(value) if value is not None else None


def persist_case_analysis(
    session: Session,
    case_analysis: CaseAnalysis,
    *,
    claim_and_fact_ids_by_run: dict[str, tuple[str, str]],
) -> None:
    """CaseAnalysis 전체(여러 run)를 저장하고 커밋한다.

    claim_and_fact_ids_by_run: run_id -> (claim_id, public_fact_id).
    ComparisonOutcome 자체에는 claim_id가 없어 pipeline 호출부에서 만든
    run_id 규칙(f"run-{case.id}-{claim.id}-{fact.id}")을 그대로 재사용한다.
    """

    now = datetime.now(timezone.utc)
    _persist_claims(session, case_analysis)
    for run in case_analysis.runs:
        run_row_id = str(uuid.uuid4())
        session.add(
            AnalysisRunRecord(
                id=run_row_id,
                logical_key=run.run_id,
                monitoring_case_id=case_analysis.monitoring_case.id,
                state=run.state.value,
                started_at=now,
                completed_at=now,
            )
        )
        for event in run.trace:
            session.add(
                TraceEventRecord(
                    run_id=run_row_id,
                    step_type=event.step_type.value,
                    stage=event.stage,
                    tool_name=event.tool_name,
                    input_summary=event.input_summary,
                    evidence=event.evidence,
                    created_at=event.created_at,
                )
            )
        if run.outcome is None:
            continue

        claim_id, fact_id = claim_and_fact_ids_by_run[run.run_id]
        comparability = run.outcome.comparability
        verdict = run.outcome.verdict

        session.add(
            ComparabilityResultRecord(
                claim_id=claim_id,
                public_fact_id=fact_id,
                comparable=comparability.comparable,
                conditions=[c.model_dump(mode="json") for c in comparability.conditions],
                missing_fields=comparability.missing_fields,
                mismatch_reasons=comparability.mismatch_reasons,
            )
        )
        session.add(
            VerdictRecord(
                run_id=run_row_id,
                claim_id=claim_id,
                public_fact_id=fact_id,
                status=verdict.status.value,
                match_type=verdict.match_type.value if verdict.match_type else None,
                claim_raw_value=_decimal_str(verdict.claim_raw_value),
                public_raw_value=_decimal_str(verdict.public_raw_value),
                claim_normalized_value=_decimal_str(verdict.claim_normalized_value),
                public_normalized_value=_decimal_str(verdict.public_normalized_value),
                absolute_difference=_decimal_str(verdict.absolute_difference),
                relative_difference_pct=_decimal_str(verdict.relative_difference_pct),
                explanation=verdict.explanation,
                review_required=verdict.review_required,
                review_reasons=verdict.review_reasons,
                follow_up_question=verdict.follow_up_question,
            )
        )

    session.commit()
