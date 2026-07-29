"""분석 실행 상태와 트레이스.

GET /runs/{id}         실행 상태
GET /runs/{id}/trace    트레이스 조회
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import AnalysisRunRecord, TraceEventRecord, VerdictRecord
from db.session import get_session

router = APIRouter(prefix="/runs", tags=["runs"])


def _get_run_or_404(session: Session, run_id: str) -> AnalysisRunRecord:
    run = session.get(AnalysisRunRecord, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="실행을 찾을 수 없습니다")
    return run


def run_summary_body(session: Session, run: AnalysisRunRecord) -> dict:
    """api/routers/cases.py의 GET /cases/{id}/runs에서도 재사용한다."""

    verdict = session.scalars(
        select(VerdictRecord).where(VerdictRecord.run_id == run.id)
    ).first()
    return {
        "id": run.id,
        "logical_key": run.logical_key,
        "monitoring_case_id": run.monitoring_case_id,
        "state": run.state,
        "started_at": run.started_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "verdict": (
            {
                "status": verdict.status,
                "match_type": verdict.match_type,
                "review_required": verdict.review_required,
            }
            if verdict is not None
            else None
        ),
    }


@router.get("/{run_id}")
def get_run(run_id: str, session: Session = Depends(get_session)) -> dict:
    run = _get_run_or_404(session, run_id)
    return run_summary_body(session, run)


@router.get("/{run_id}/trace")
def get_run_trace(run_id: str, session: Session = Depends(get_session)) -> list[dict]:
    _get_run_or_404(session, run_id)
    events = session.scalars(
        select(TraceEventRecord)
        .where(TraceEventRecord.run_id == run_id)
        .order_by(TraceEventRecord.created_at)
    ).all()
    return [
        {
            "step_type": event.step_type,
            "stage": event.stage,
            "tool_name": event.tool_name,
            "input_summary": event.input_summary,
            "evidence": event.evidence,
            "created_at": event.created_at.isoformat(),
        }
        for event in events
    ]
