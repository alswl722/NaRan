"""사후관리 대기열과 사례 조회.

GET /cases            대기열
GET /cases/{id}        사례·보고서·현재 상태
POST /cases/{id}/analyze  분석 실행
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.session import get_session

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("")
def list_cases(session: Session = Depends(get_session)) -> list[dict]:
    """대기열 정렬: review_required → 다음 점검일 → 중요도 (claude.md 9절)."""
    raise HTTPException(status_code=501, detail="구현 예정")


@router.get("/{case_id}")
def get_case(case_id: str, session: Session = Depends(get_session)) -> dict:
    raise HTTPException(status_code=501, detail="구현 예정")


@router.post("/{case_id}/analyze")
def analyze_case(case_id: str, session: Session = Depends(get_session)) -> dict:
    """api.agent.pipeline / orchestrator를 호출해 분석을 실행한다."""
    raise HTTPException(status_code=501, detail="구현 예정")
