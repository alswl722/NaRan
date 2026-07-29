"""사례 단위 분석 실행 직렬화.

같은 case_id에 대한 동시 /cases/{id}/analyze 호출이 DB에 중복 run을
쌓거나 서로 다른 프로세스가 같은 fixture를 겹쳐 읽는 것을 막는다.
단일 프로세스(uvicorn 1워커) 데모 규모를 전제한다.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from contextlib import contextmanager
from collections.abc import Iterator

from fastapi import HTTPException

_guard = threading.Lock()
_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)


@contextmanager
def case_analysis_lock(case_id: str) -> Iterator[None]:
    """비블로킹 획득 — 이미 실행 중이면 409."""
    with _guard:
        lock = _locks[case_id]
    if not lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="이미 분석이 실행 중입니다 — 완료 후 다시 시도하세요")
    try:
        yield
    finally:
        lock.release()
