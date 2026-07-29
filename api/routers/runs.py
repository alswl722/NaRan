"""분석 실행 상태와 트레이스.

GET /runs/{id}         실행 상태
GET /runs/{id}/trace    트레이스 조회
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.session import get_session

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("/{run_id}")
def get_run(run_id: str, session: Session = Depends(get_session)) -> dict:
    raise HTTPException(status_code=501, detail="구현 예정")


@router.get("/{run_id}/trace")
def get_run_trace(run_id: str, session: Session = Depends(get_session)) -> list[dict]:
    raise HTTPException(status_code=501, detail="구현 예정")
