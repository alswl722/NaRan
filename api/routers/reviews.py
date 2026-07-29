"""담당자 HITL 조치와 감사 이력.

POST /reviews                    담당자 조치 추가 (append-only)
GET /reviews/{case_id}/history    감사 이력 조회

담당자 조치는 AI Verdict를 절대 덮어쓰지 않는다 (claude.md 6절, 18절).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.session import get_session

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.post("")
def create_review(session: Session = Depends(get_session)) -> dict:
    raise HTTPException(status_code=501, detail="구현 예정")


@router.get("/{case_id}/history")
def get_review_history(case_id: str, session: Session = Depends(get_session)) -> list[dict]:
    raise HTTPException(status_code=501, detail="구현 예정")
