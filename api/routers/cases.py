"""사후관리 대기열과 사례 조회.

GET /cases            대기열
GET /cases/{id}        사례·보고서·현재 상태
POST /cases/{id}/analyze  분석 실행
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.agent.case_lock import case_analysis_lock
from api.agent.llm_extract import VerifiedClaimCache
from api.agent.persist import persist_case_analysis
from api.agent.pipeline import CaseAnalysis, analyze_verified_case
from api.routers.runs import run_summary_body
from db.models import (
    AnalysisRunRecord,
    Claim,
    Company,
    MonitoringCaseRecord,
    Report,
    VerdictRecord,
)
from db.session import get_session

router = APIRouter(prefix="/cases", tags=["cases"])

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"

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
    claim_ids = session.scalars(
        select(Claim.id).where(Claim.report_id == case.report_id)
    ).all()
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
        "claim_ids": list(claim_ids),
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


@router.get("/{case_id}/runs")
def list_case_runs(case_id: str, session: Session = Depends(get_session)) -> list[dict]:
    """이 사례에 속한 모든 실행을 최신순으로 반환한다.

    프론트가 각 run의 /runs/{id}/trace를 추가로 불러 장면 2(비교 가능성
    트레이스)를 구성할 때 쓴다.
    """

    case = session.get(MonitoringCaseRecord, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="사례를 찾을 수 없습니다")
    runs = session.scalars(
        select(AnalysisRunRecord)
        .where(AnalysisRunRecord.monitoring_case_id == case_id)
        .order_by(AnalysisRunRecord.started_at.desc())
    ).all()
    return [run_summary_body(session, run) for run in runs]


def _find_case_fixture(case_id: str) -> dict:
    for path in sorted(FIXTURES_DIR.glob("sample_case_*.json")):
        case_data = json.loads(path.read_text(encoding="utf-8"))
        if case_data["monitoring_case"]["id"] == case_id:
            return case_data
    raise HTTPException(status_code=404, detail="사례를 찾을 수 없습니다")


def _map_runs_to_claim_and_fact(case_analysis: CaseAnalysis) -> dict[str, tuple[str, str]]:
    """run_id 접두어(run-{case_id}-{claim_id}-{fact_id})로 claim/fact를 되짚는다.

    ComparisonOutcome 자체는 claim_id를 담지 않으므로, pipeline이 만든
    run_id 규칙을 그대로 재사용해 역매핑한다 (api/agent/pipeline.py 참고).
    """

    case_prefix = f"run-{case_analysis.monitoring_case.id}-"
    claims = [
        claim for extraction in case_analysis.extractions for claim in extraction.claims
    ]
    mapping: dict[str, tuple[str, str]] = {}
    for run in case_analysis.runs:
        if not run.run_id.startswith(case_prefix):
            raise ValueError(f"예상하지 못한 run_id 형식입니다: {run.run_id}")
        remainder = run.run_id[len(case_prefix) :]
        matched: tuple[str, str] | None = None
        for claim in claims:
            claim_prefix = f"{claim.id}-"
            if remainder.startswith(claim_prefix):
                fact_id = remainder[len(claim_prefix) :]
                if any(fact.id == fact_id for fact in case_analysis.public_facts):
                    matched = (claim.id, fact_id)
                    break
        if matched is None:
            raise ValueError(f"run_id에서 claim/fact를 역매핑할 수 없습니다: {run.run_id}")
        mapping[run.run_id] = matched
    return mapping


@router.post("/{case_id}/analyze")
def analyze_case(case_id: str, session: Session = Depends(get_session)) -> dict:
    """검증 fixture와 api.agent.pipeline.analyze_verified_case로 분석을 실행한다."""

    case = session.get(MonitoringCaseRecord, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="사례를 찾을 수 없습니다")

    case_data = _find_case_fixture(case_id)

    with case_analysis_lock(case_id):
        cache = VerifiedClaimCache.from_fixture_directory(FIXTURES_DIR)
        case_analysis = analyze_verified_case(case_data, cache=cache)
        claim_and_fact_ids_by_run = _map_runs_to_claim_and_fact(case_analysis)
        persist_case_analysis(
            session,
            case_analysis,
            claim_and_fact_ids_by_run=claim_and_fact_ids_by_run,
        )

    return _case_summary(session, case)
