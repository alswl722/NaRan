"""공개 데이터 수동 갱신.

POST /public-data/refresh  갱신 시도, 실패 시 기존 저장본으로 계속 분석 (claude.md 15절)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.session import get_session

router = APIRouter(prefix="/public-data", tags=["public-data"])


@router.post("/refresh")
def refresh_public_data(session: Session = Depends(get_session)) -> dict:
    raise HTTPException(status_code=501, detail="구현 예정")
