"""공개 데이터 수동 갱신.

POST /public-data/refresh  새 PublicFact 버전을 저장. 실제 live scraping은
아직 연결하지 않는다 — db/envinfo.py는 claude.md 16절이 지목한 대로
PublicFact 계약에 필요한 필드가 부족하고 검증되지 않은 휴리스틱을 포함하고
있어, 그 문제를 먼저 고치기 전까지는 API가 직접 호출하지 않는다. 지금은
이미 검증된 PublicFact 값을 받아 버전 저장·조회 메커니즘만 제공한다
(claude.md 15절: 이전 값을 덮어쓰지 않고 새 버전을 추가한다).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Company, PublicFact as PublicFactRecord
from db.session import get_session
from naran.contracts import PublicFact

router = APIRouter(prefix="/public-data", tags=["public-data"])


def _latest_matching_fact(
    session: Session, fact: PublicFact
) -> PublicFactRecord | None:
    """같은 대상(회사·사업장·지표·Scope·기간)의 기존 최신 버전을 찾는다."""

    candidates = session.scalars(
        select(PublicFactRecord).where(
            PublicFactRecord.company_id == fact.company_id,
            PublicFactRecord.site_id == fact.site_id,
            PublicFactRecord.metric == fact.metric,
            PublicFactRecord.scope == (fact.scope.value if fact.scope else None),
            PublicFactRecord.period_start == fact.period_start,
            PublicFactRecord.period_end == fact.period_end,
        )
    ).all()
    if not candidates:
        return None
    return max(candidates, key=lambda record: record.retrieved_at)


def _fact_body(fact: PublicFactRecord) -> dict:
    return {
        "id": fact.id,
        "version": fact.version,
        "raw_value": str(fact.raw_value) if fact.raw_value is not None else None,
        "normalized_value": (
            str(fact.normalized_value) if fact.normalized_value is not None else None
        ),
        "source_url": fact.source_url,
        "retrieved_at": fact.retrieved_at.isoformat(),
        "source_hash": fact.source_hash,
    }


@router.post("/refresh")
def refresh_public_data(
    fact_data: dict, session: Session = Depends(get_session)
) -> dict:
    """검증된 PublicFact 값을 새 버전으로 저장한다.

    갱신 "성공"은 새 버전 저장이 끝났다는 뜻이다. company_id가 DB에 없으면
    404를 반환하고 저장하지 않는다 — 존재하지 않는 대상에 새 버전을 붙이지
    않기 위함이다. id가 이미 있는 버전이면(동일 fixture 재적재 등) 저장을
    건너뛰고 기존 값을 그대로 반환한다.
    """

    try:
        fact = PublicFact.model_validate(fact_data)
    except Exception as exc:  # Pydantic ValidationError를 422로 변환
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if session.get(Company, fact.company_id) is None:
        raise HTTPException(status_code=404, detail="공개 데이터 대상 기업을 찾을 수 없습니다")

    previous = _latest_matching_fact(session, fact)

    if session.get(PublicFactRecord, fact.id) is not None:
        return {
            "status": "skipped",
            "reason": "이미 저장된 버전입니다",
            "current": _fact_body(session.get(PublicFactRecord, fact.id)),
        }

    record = PublicFactRecord(
        id=fact.id,
        company_id=fact.company_id,
        site_id=fact.site_id,
        entity_level=fact.entity_level.value,
        metric=fact.metric,
        raw_value=fact.raw_value,
        normalized_value=fact.normalized_value,
        unit=fact.unit,
        value_basis=fact.value_basis.value if fact.value_basis else None,
        period_start=fact.period_start,
        period_end=fact.period_end,
        scope=fact.scope.value if fact.scope else None,
        scope2_method=fact.scope2_method.value if fact.scope2_method else None,
        organization_boundary=(
            fact.organization_boundary.value if fact.organization_boundary else None
        ),
        geographic_boundary=fact.geographic_boundary,
        display_decimal_places=fact.display_decimal_places,
        display_rule=fact.display_rule,
        disclosure_duty=fact.disclosure_duty.value,
        source_url=fact.source_url,
        retrieved_at=fact.retrieved_at,
        source_hash=fact.source_hash,
        version=fact.version,
    )
    session.add(record)
    session.commit()

    return {
        "status": "added",
        "previous": _fact_body(previous) if previous else None,
        "current": _fact_body(record),
    }
