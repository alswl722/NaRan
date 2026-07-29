"""SQLAlchemy 엔진과 세션 의존성.

DATABASE_URL 미설정 시 로컬 SQLite 파일로 폴백한다 — API 키와 네트워크
없이도 A·B·C가 재현돼야 한다는 완료 조건(claude.md 24절)에 맞춘 것이다.
Postgres 등 실제 DB를 쓰려면 .env에 DATABASE_URL을 명시한다.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

DEFAULT_SQLITE_URL = "sqlite:///./naran.db"

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """엔진 싱글턴. DATABASE_URL 미설정 시 로컬 SQLite로 폴백한다."""
    global _engine, _SessionLocal
    if _engine is None:
        database_url = os.getenv("DATABASE_URL") or DEFAULT_SQLITE_URL
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        engine_kwargs: dict = {"connect_args": connect_args}
        if not database_url.startswith("sqlite"):
            engine_kwargs.update(pool_size=5, pool_pre_ping=True)
        _engine = create_engine(database_url, **engine_kwargs)
        _SessionLocal = sessionmaker(bind=_engine, class_=Session, expire_on_commit=False)
    return _engine


def get_session() -> Iterator[Session]:
    """FastAPI 의존성: 요청 스코프 세션."""
    get_engine()
    assert _SessionLocal is not None
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()
