"""담당자 HITL 조치와 감사 이력.

POST /reviews                    담당자 조치 추가 (append-only)
GET /reviews/{case_id}/history    감사 이력 조회

담당자 조치는 AI Verdict를 절대 덮어쓰지 않는다 (claude.md 6절, 18절).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import (
    AnalysisRunRecord,
    HumanReviewRecord,
    MonitoringCaseRecord,
    ReviewItemResolutionRecord,
    VerdictRecord,
)
from db.session import get_session
from naran.contracts import ReviewAction

router = APIRouter(prefix="/reviews", tags=["reviews"])

_ALLOWED_ACTIONS = {action.value for action in ReviewAction}
_ALLOWED_ITEM_RESOLUTIONS = {"확인 완료", "추가 자료 요청"}


class CreateReviewRequest(BaseModel):
    case_id: str
    action: str
    note: str
    reviewer: str = Field(min_length=1)


class CreateReviewItemResolutionRequest(BaseModel):
    case_id: str
    verdict_id: str
    claim_id: str
    review_reason: str = Field(min_length=1)
    resolution: str
    note: str = Field(min_length=1)
    reviewer: str = Field(min_length=1)


def ensure_review_item_table(session: Session) -> None:
    """기존 데모 SQLite에도 신규 append-only 테이블을 안전하게 추가한다."""

    ReviewItemResolutionRecord.__table__.create(
        bind=session.get_bind(), checkfirst=True
    )


def latest_item_resolutions(
    session: Session, verdict_id: str
) -> dict[str, ReviewItemResolutionRecord]:
    ensure_review_item_table(session)
    records = session.scalars(
        select(ReviewItemResolutionRecord)
        .where(ReviewItemResolutionRecord.verdict_id == verdict_id)
        .order_by(ReviewItemResolutionRecord.processed_at)
    ).all()
    return {record.review_reason: record for record in records}


def _item_resolution_body(record: ReviewItemResolutionRecord) -> dict:
    return {
        "id": record.id,
        "case_id": record.case_id,
        "verdict_id": record.verdict_id,
        "claim_id": record.claim_id,
        "review_reason": record.review_reason,
        "resolution": record.resolution,
        "note": record.note,
        "reviewer": record.reviewer,
        "processed_at": record.processed_at.isoformat(),
    }


def _latest_review(session: Session, case_id: str) -> HumanReviewRecord | None:
    return session.scalars(
        select(HumanReviewRecord)
        .where(HumanReviewRecord.case_id == case_id)
        .order_by(HumanReviewRecord.processed_at.desc())
    ).first()


def _latest_follow_up_question(session: Session, case_id: str) -> str | None:
    """이 사례의 가장 최근 실행에서 나온 follow_up_question을 찾는다.

    새 질문을 만들지 않고 orchestrator/compare_engine이 이미 계산해 둔
    Verdict.follow_up_question을 그대로 노출한다 (claude.md: LLM/새 로직이
    최종 판정·질문을 재생성하지 않는다).
    """

    run_ids = session.scalars(
        select(AnalysisRunRecord.id)
        .where(AnalysisRunRecord.monitoring_case_id == case_id)
        .order_by(AnalysisRunRecord.started_at.desc())
    ).all()
    if not run_ids:
        return None
    verdicts = session.scalars(
        select(VerdictRecord)
        .where(VerdictRecord.run_id.in_(run_ids))
        .where(VerdictRecord.follow_up_question.is_not(None))
    ).all()
    if not verdicts:
        return None
    return verdicts[0].follow_up_question


def _review_body(review: HumanReviewRecord) -> dict:
    return {
        "id": review.id,
        "case_id": review.case_id,
        "action": review.action,
        "note": review.note,
        "reviewer": review.reviewer,
        "processed_at": review.processed_at.isoformat(),
        "previous_action": review.previous_action,
    }


@router.post("")
def create_review(
    body: CreateReviewRequest, session: Session = Depends(get_session)
) -> dict:
    if body.action not in _ALLOWED_ACTIONS:
        raise HTTPException(
            status_code=422,
            detail=f"action은 {sorted(_ALLOWED_ACTIONS)} 중 하나여야 합니다",
        )
    case = session.get(MonitoringCaseRecord, body.case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="사례를 찾을 수 없습니다")

    previous = _latest_review(session, body.case_id)
    review = HumanReviewRecord(
        case_id=body.case_id,
        action=body.action,
        note=body.note,
        reviewer=body.reviewer,
        processed_at=datetime.now(timezone.utc),
        previous_action=previous.action if previous else None,
    )
    session.add(review)
    session.commit()

    response = _review_body(review)
    if body.action == ReviewAction.REQUEST_INFORMATION.value:
        response["follow_up_question"] = _latest_follow_up_question(
            session, body.case_id
        )
    return response


@router.post("/items")
def create_review_item_resolution(
    body: CreateReviewItemResolutionRequest,
    session: Session = Depends(get_session),
) -> dict:
    ensure_review_item_table(session)
    if body.resolution not in _ALLOWED_ITEM_RESOLUTIONS:
        raise HTTPException(
            status_code=422,
            detail=f"resolution은 {sorted(_ALLOWED_ITEM_RESOLUTIONS)} 중 하나여야 합니다",
        )
    case = session.get(MonitoringCaseRecord, body.case_id)
    verdict = session.get(VerdictRecord, body.verdict_id)
    if case is None:
        raise HTTPException(status_code=404, detail="사례를 찾을 수 없습니다")
    if verdict is None or verdict.claim_id != body.claim_id:
        raise HTTPException(status_code=404, detail="판정 항목을 찾을 수 없습니다")
    if body.review_reason not in verdict.review_reasons:
        raise HTTPException(status_code=422, detail="판정에 없는 확인 사유입니다")

    run = session.get(AnalysisRunRecord, verdict.run_id)
    if run is None or run.monitoring_case_id != body.case_id:
        raise HTTPException(status_code=422, detail="사례와 판정이 일치하지 않습니다")

    record = ReviewItemResolutionRecord(
        case_id=body.case_id,
        verdict_id=body.verdict_id,
        claim_id=body.claim_id,
        review_reason=body.review_reason,
        resolution=body.resolution,
        note=body.note,
        reviewer=body.reviewer,
        processed_at=datetime.now(timezone.utc),
    )
    session.add(record)
    session.commit()
    return _item_resolution_body(record)


@router.get("/{case_id}/items")
def get_review_item_history(
    case_id: str, session: Session = Depends(get_session)
) -> list[dict]:
    ensure_review_item_table(session)
    if session.get(MonitoringCaseRecord, case_id) is None:
        raise HTTPException(status_code=404, detail="사례를 찾을 수 없습니다")
    records = session.scalars(
        select(ReviewItemResolutionRecord)
        .where(ReviewItemResolutionRecord.case_id == case_id)
        .order_by(ReviewItemResolutionRecord.processed_at)
    ).all()
    return [_item_resolution_body(record) for record in records]


@router.get("/{case_id}/history")
def get_review_history(case_id: str, session: Session = Depends(get_session)) -> list[dict]:
    case = session.get(MonitoringCaseRecord, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="사례를 찾을 수 없습니다")
    reviews = session.scalars(
        select(HumanReviewRecord)
        .where(HumanReviewRecord.case_id == case_id)
        .order_by(HumanReviewRecord.processed_at)
    ).all()
    return [_review_body(review) for review in reviews]
