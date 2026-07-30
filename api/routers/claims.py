"""주장·근거·비교 결과 조회.

GET /claims/{id}  주장 원문·페이지·출처와 대응하는 비교 결과 전부
"""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.routers.reviews import latest_item_resolutions
from db.entity_map import DEFAULT_ENTITY_MAP, SourceSystem
from db.models import (
    AnalysisRunRecord,
    Claim as ClaimRecord,
    ComparabilityResultRecord,
    PublicFact as PublicFactRecord,
    Report as ReportRecord,
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


def _source_system(source_url: str) -> SourceSystem | None:
    hostname = urlparse(source_url).hostname
    if hostname in {"env-info.kr", "www.env-info.kr"}:
        return SourceSystem.ENV_INFO
    if hostname in {"gir.go.kr", "www.gir.go.kr"}:
        return SourceSystem.GIR
    return None


def _boundary_mapping_body(
    session: Session,
    claim: ClaimRecord,
    fact: PublicFactRecord,
) -> dict | None:
    """비교에 실제 사용한 기업·사업장 범위 매핑 근거를 화면에 전달한다."""

    if fact.site_id is None or not claim.period_start:
        return None
    source_system = _source_system(fact.source_url)
    report = session.get(ReportRecord, claim.report_id)
    if source_system is None or report is None:
        return None
    try:
        year = int(claim.period_start[:4])
    except ValueError:
        return None
    mapping = DEFAULT_ENTITY_MAP.find(
        source_system=source_system,
        source_entity_id=fact.site_id,
        company_id=report.company_id,
        year=year,
    )
    if mapping is None:
        return None
    return {
        "source_entity_name": mapping.source_entity_name,
        "alignment_permitted": mapping.permits_boundary_alignment(year),
        "evidence": list(mapping.evidence),
        "note": mapping.note,
        "valid_from_year": mapping.valid_from_year,
        "valid_to_year": mapping.valid_to_year,
    }


def _verdict_body(session: Session, verdict: VerdictRecord) -> dict:
    resolutions = latest_item_resolutions(session, verdict.id)
    return {
        "id": verdict.id,
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
        "review_resolutions": {
            reason: {
                "resolution": record.resolution,
                "note": record.note,
                "reviewer": record.reviewer,
                "processed_at": record.processed_at.isoformat(),
            }
            for reason, record in resolutions.items()
        },
    }


@router.get("/{claim_id}")
def get_claim(claim_id: str, session: Session = Depends(get_session)) -> dict:
    claim = session.get(ClaimRecord, claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail="주장을 찾을 수 없습니다")

    comparisons: list[dict] = []
    all_verdicts = session.scalars(
        select(VerdictRecord)
        .join(AnalysisRunRecord, VerdictRecord.run_id == AnalysisRunRecord.id)
        .where(VerdictRecord.claim_id == claim_id)
        .order_by(AnalysisRunRecord.started_at.desc())
    ).all()
    seen_fact_ids: set[str] = set()
    for verdict in all_verdicts:
        # 같은 공개 데이터에 대한 재분석 결과는 가장 최신 판정만 현재 화면에
        # 노출한다. 이전 판정·실행은 run 트레이스와 감사 이력에 그대로 남는다.
        if verdict.public_fact_id in seen_fact_ids:
            continue
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
                "boundary_mapping": (
                    _boundary_mapping_body(session, claim, fact) if fact else None
                ),
                "comparability": (
                    _comparability_body(comparability) if comparability else None
                ),
                "verdict": _verdict_body(session, verdict),
            }
        )

    return {
        "claim": _claim_body(claim),
        "comparisons": comparisons,
        "analyzed": bool(comparisons),
    }
