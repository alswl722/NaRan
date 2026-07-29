"""주장·근거·비교 결과 조회.

GET /claims/{id}  주장 원문·페이지·출처와 대응하는 비교 결과 전부
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import (
    Claim as ClaimRecord,
    ComparabilityResultRecord,
    PublicFact as PublicFactRecord,
    VerdictRecord,
)
from db.session import get_session

router = APIRouter(prefix="/claims", tags=["claims"])


def _claim_body(claim: ClaimRecord) -> dict:
    return {
        "id": claim.id,
        "report_id": claim.report_id,
        "claim_type": claim.claim_type,
        "metric": claim.metric,
        "value": str(claim.value) if claim.value is not None else None,
        "unit": claim.unit,
        "value_basis": claim.value_basis,
        "period_start": claim.period_start,
        "period_end": claim.period_end,
        "baseline_year": claim.baseline_year,
        "target_year": claim.target_year,
        "scope": claim.scope,
        "scope2_method": claim.scope2_method,
        "organization_boundary": claim.organization_boundary,
        "geographic_boundary": claim.geographic_boundary,
        "entity_level": claim.entity_level,
        "raw_text": claim.raw_text,
        "page": claim.page,
        "evidence": claim.evidence,
        "confidence": claim.confidence,
        "extraction_mode": claim.extraction_mode,
    }


def _public_fact_body(fact: PublicFactRecord) -> dict:
    return {
        "id": fact.id,
        "company_id": fact.company_id,
        "site_id": fact.site_id,
        "entity_level": fact.entity_level,
        "metric": fact.metric,
        "raw_value": str(fact.raw_value) if fact.raw_value is not None else None,
        "normalized_value": (
            str(fact.normalized_value) if fact.normalized_value is not None else None
        ),
        "unit": fact.unit,
        "scope": fact.scope,
        "scope2_method": fact.scope2_method,
        "organization_boundary": fact.organization_boundary,
        "geographic_boundary": fact.geographic_boundary,
        "display_decimal_places": fact.display_decimal_places,
        "display_rule": fact.display_rule,
        "disclosure_duty": fact.disclosure_duty,
        "source_url": fact.source_url,
        "retrieved_at": fact.retrieved_at.isoformat(),
        "source_hash": fact.source_hash,
        "version": fact.version,
    }


def _comparability_body(result: ComparabilityResultRecord) -> dict:
    return {
        "comparable": result.comparable,
        "conditions": result.conditions,
        "missing_fields": result.missing_fields,
        "mismatch_reasons": result.mismatch_reasons,
    }


def _verdict_body(verdict: VerdictRecord) -> dict:
    return {
        "status": verdict.status,
        "match_type": verdict.match_type,
        "claim_raw_value": verdict.claim_raw_value,
        "public_raw_value": verdict.public_raw_value,
        "claim_normalized_value": verdict.claim_normalized_value,
        "public_normalized_value": verdict.public_normalized_value,
        "absolute_difference": verdict.absolute_difference,
        "relative_difference_pct": verdict.relative_difference_pct,
        "explanation": verdict.explanation,
        "review_required": verdict.review_required,
        "review_reasons": verdict.review_reasons,
        "follow_up_question": verdict.follow_up_question,
    }


@router.get("/{claim_id}")
def get_claim(claim_id: str, session: Session = Depends(get_session)) -> dict:
    claim = session.get(ClaimRecord, claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail="주장을 찾을 수 없습니다")

    comparisons: list[dict] = []
    verdicts = session.scalars(
        select(VerdictRecord).where(VerdictRecord.claim_id == claim_id)
    ).all()
    seen_fact_ids: set[str] = set()
    for verdict in verdicts:
        seen_fact_ids.add(verdict.public_fact_id)
        fact = session.get(PublicFactRecord, verdict.public_fact_id)
        comparability = session.scalars(
            select(ComparabilityResultRecord).where(
                ComparabilityResultRecord.claim_id == claim_id,
                ComparabilityResultRecord.public_fact_id == verdict.public_fact_id,
            )
        ).first()
        comparisons.append(
            {
                "public_fact": _public_fact_body(fact) if fact else None,
                "comparability": (
                    _comparability_body(comparability) if comparability else None
                ),
                "verdict": _verdict_body(verdict),
            }
        )

    return {
        "claim": _claim_body(claim),
        "comparisons": comparisons,
        "analyzed": bool(comparisons),
    }
