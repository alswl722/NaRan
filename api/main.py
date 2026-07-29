"""나란 FastAPI 앱.

라우터: /cases(사후관리 대기열·분석 실행), /runs(실행 상태·트레이스),
/claims(주장·근거·비교 결과), /reviews(HITL 조치·감사 이력),
/public-data(공개 데이터 수동 갱신).
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from api.routers import cases, claims, public_data, reviews, runs
from db.session import get_engine

app = FastAPI(title="나란 API", version="0.1.0")

_extra_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        *_extra_origins,
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cases.router)
app.include_router(runs.router)
app.include_router(claims.router)
app.include_router(reviews.router)
app.include_router(public_data.router)


@app.get("/health")
def health() -> dict:
    """Liveness — DB를 건드리지 않는다."""
    return {"status": "ok"}


@app.get("/health/db", response_model=None)
def health_db() -> JSONResponse | dict:
    """Readiness — DB에 SELECT 1. DATABASE_URL 미설정·연결 실패를 조기에 드러낸다."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected"}
    except Exception as exc:  # noqa: BLE001 — 헬스체크는 원인 문자열만 노출
        return JSONResponse(
            status_code=503,
            content={"status": "error", "db": "unavailable", "detail": str(exc)},
        )
