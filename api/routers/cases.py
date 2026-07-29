"""사후관리 대기열과 사례 조회.

GET /cases            대기열
GET /cases/{id}        사례·보고서·현재 상태
POST /cases/{id}/analyze  분석 실행
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import (
    AnalysisRunRecord,
    Company,
    MonitoringCaseRecord,
    Report,
    VerdictRecord,
)
from db.session import get_session

router = APIRouter(prefix="/cases", tags=["cases"])

_IMPORTANCE_ORDER = {"높음": 0, "보통": 1, "낮음": 2}


def _case_review_required(session: Session, case_id: str) -> bool | None:
    """이 사례에 속한 실행들 중 하나라도 review_required가 있으면 true.

    아직 분석을 한 번도 실행하지 않은 사례는 None(미분석)을 반환한다 —
    분석 전 상태를 review_required=false로 오인시키지 않기 위함이다.
    """

    run_ids = session.scalars(
        select(AnalysisRunRecord.id).where(
            AnalysisRunRecord.monitoring_case_id == case_id
        )
    ).all()
    if not run_ids:
        return None
    verdicts = session.scalars(
        select(VerdictRecord.review_required).where(VerdictRecord.run_id.in_(run_ids))
    ).all()
    if not verdicts:
        return None
    return any(verdicts)


def _case_summary(session: Session, case: MonitoringCaseRecord) -> dict:
    company = session.get(Company, case.company_id)
    report = session.get(Report, case.report_id)
    return {
        "id": case.id,
        "company_id": case.company_id,
        "company_name": company.legal_name if company else None,
        "report_id": case.report_id,
        "report_title": report.title if report else None,
        "case_type": case.case_type,
        "next_review_date": case.next_review_date,
        "importance": case.importance,
        "synthetic": case.synthetic,
        "review_required": _case_review_required(session, case.id),
    }


def _sort_key(summary: dict) -> tuple:
    review_required = summary["review_required"]
    # None(미분석)과 False(검토 불필요)는 True(검토 필요) 다음 순위.
    review_rank = 0 if review_required else 1
    return (
        review_rank,
        summary["next_review_date"],
        _IMPORTANCE_ORDER.get(summary["importance"], 99),
    )


@router.get("")
def list_cases(session: Session = Depends(get_session)) -> list[dict]:
    """대기열 정렬: review_required → 다음 점검일 → 중요도 (claude.md 9절)."""
    cases = session.scalars(select(MonitoringCaseRecord)).all()
    summaries = [_case_summary(session, case) for case in cases]
    summaries.sort(key=_sort_key)
    return summaries


@router.get("/{case_id}")
def get_case(case_id: str, session: Session = Depends(get_session)) -> dict:
    case = session.get(MonitoringCaseRecord, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="사례를 찾을 수 없습니다")
    return _case_summary(session, case)


@router.post("/{case_id}/analyze")
def analyze_case(case_id: str, session: Session = Depends(get_session)) -> dict:
    """api.agent.pipeline / orchestrator를 호출해 분석을 실행한다."""
    raise HTTPException(status_code=501, detail="구현 예정")
