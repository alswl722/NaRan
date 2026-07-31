"""사례 분석 중 프론트엔드에 보여줄 실제 진행 상태.

분석 POST가 끝날 때까지 기다리는 동안 별도 GET 요청으로 조회한다. 데모는
uvicorn 단일 프로세스로 실행하므로 프로세스 메모리에만 보관하고, 판정·감사
데이터와는 섞지 않는다.
"""

from __future__ import annotations

from datetime import datetime, timezone
import threading

_lock = threading.Lock()
_progress: dict[str, dict] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def start(case_id: str, *, mode: str, total: int) -> None:
    now = _now()
    with _lock:
        _progress[case_id] = {
            "case_id": case_id,
            "status": "running",
            "mode": mode,
            "current": 0,
            "total": total,
            "events": [],
            "started_at": now,
            "finished_at": None,
        }


def add(
    case_id: str,
    *,
    step_type: str,
    stage: str,
    tool_name: str | None,
    message: str,
) -> None:
    with _lock:
        progress = _progress.get(case_id)
        if progress is None:
            return
        progress["current"] = min(progress["current"] + 1, progress["total"])
        progress["events"].append(
            {
                "id": len(progress["events"]) + 1,
                "step_type": step_type,
                "stage": stage,
                "tool_name": tool_name,
                "message": message,
                "created_at": _now(),
            }
        )


def complete(case_id: str, *, message: str) -> None:
    add(
        case_id,
        step_type="행동",
        stage="분석 완료",
        tool_name="result.persist",
        message=message,
    )
    with _lock:
        progress = _progress.get(case_id)
        if progress is not None:
            progress["status"] = "completed"
            progress["current"] = progress["total"]
            progress["finished_at"] = _now()


def fail(case_id: str, *, message: str) -> None:
    with _lock:
        progress = _progress.get(case_id)
        if progress is None:
            return
        progress["status"] = "failed"
        progress["finished_at"] = _now()
        progress["events"].append(
            {
                "id": len(progress["events"]) + 1,
                "step_type": "관찰",
                "stage": "분석 실패",
                "tool_name": None,
                "message": message,
                "created_at": _now(),
            }
        )


def get(case_id: str) -> dict:
    with _lock:
        progress = _progress.get(case_id)
        if progress is None:
            return {
                "case_id": case_id,
                "status": "idle",
                "mode": None,
                "current": 0,
                "total": 0,
                "events": [],
                "started_at": None,
                "finished_at": None,
            }
        return {
            **progress,
            "events": [dict(event) for event in progress["events"]],
        }
