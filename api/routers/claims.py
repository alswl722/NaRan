"""주장·근거·비교 결과 조회.

GET /claims/{id}  주장 원문·페이지·비교 결과
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.session import get_session

router = APIRouter(prefix="/claims", tags=["claims"])


@router.get("/{claim_id}")
def get_claim(claim_id: str, session: Session = Depends(get_session)) -> dict:
    raise HTTPException(status_code=501, detail="구현 예정")
