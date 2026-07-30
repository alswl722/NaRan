"""사후관리 대기열과 사례 조회.

GET /cases            대기열
GET /cases/{id}        사례·보고서·현재 상태
POST /cases/{id}/analyze  분석 실행
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.agent.case_lock import case_analysis_lock
from api.agent.document_extract import extract_document_page
from api.agent.gemini_client import (
    GeminiConfigurationError,
    GeminiStructuredClaimClient,
)
from api.agent.llm_extract import VerifiedClaimCache
from api.agent.persist import persist_case_analysis
from api.agent.pipeline import (
    CaseAnalysis,
    analyze_case_extractions,
    analyze_verified_case,
)
from api.agent.orchestrator import RunState
from api.routers.reviews import latest_item_resolutions
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
from naran.contracts import ExecutionMode, Report as ReportContract

router = APIRouter(prefix="/cases", tags=["cases"])

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"
REFERENCES_DIR = Path(__file__).resolve().parents[2] / "references"
REPORT_PDF_BY_ID = {
    "report-a-2024": "Samsung-Biologics-2025-ESG-Report_KR.pdf",
    "report-b-2024": "Samsung_Electronics_Sustainability_Report_2025_ENG.pdf",
}
# 데모 live 호출 범위. A의 p.220은 검증의견서 근거로 계속 보존하지만,
# 수치 Claim을 추출할 페이지가 아니므로 Gemini 호출 대상에서는 제외한다.
LIVE_EXTRACTION_PAGES_BY_REPORT = {
    "report-a-2024": (171, 172),
    "report-b-2024": (68,),
}

_IMPORTANCE_ORDER = {"높음": 0, "보통": 1, "낮음": 2}


class AnalyzeCaseRequest(BaseModel):
    mode: Literal["demo", "live"] = "demo"
    allow_cache_fallback: bool = True


def _case_review_required(session: Session, case_id: str) -> bool | None:
    """최신 판정에 미처리 확인 사항이 하나라도 있으면 true.

    아직 분석을 한 번도 실행하지 않은 사례는 None(미분석)을 반환한다 —
    분석 전 상태를 review_required=false로 오인시키지 않기 위함이다.
    AI의 원본 판정은 유지하고 별도 담당자 처리 이력만 반영한다.
    """

    rows = session.execute(
        select(VerdictRecord, AnalysisRunRecord.started_at)
        .join(AnalysisRunRecord, VerdictRecord.run_id == AnalysisRunRecord.id)
        .where(AnalysisRunRecord.monitoring_case_id == case_id)
        .order_by(AnalysisRunRecord.started_at.desc())
    ).all()
    if not rows:
        return None

    latest_by_comparison: dict[tuple[str, str], VerdictRecord] = {}
    for verdict, _started_at in rows:
        latest_by_comparison.setdefault(
            (verdict.claim_id, verdict.public_fact_id), verdict
        )

    for verdict in latest_by_comparison.values():
        if not verdict.review_required:
            continue
        if not verdict.review_reasons:
            return True
        resolutions = latest_item_resolutions(session, verdict.id)
        if any(
            resolutions.get(reason) is None
            or resolutions[reason].resolution != "확인 완료"
            for reason in verdict.review_reasons
        ):
            return True
    return False


def _case_summary(session: Session, case: MonitoringCaseRecord) -> dict:
    company = session.get(Company, case.company_id)
    report = session.get(Report, case.report_id)
    latest_started_at = session.scalar(
        select(func.max(AnalysisRunRecord.started_at)).where(
            AnalysisRunRecord.monitoring_case_id == case.id
        )
    )
    claim_ids: list[str]
    if latest_started_at is not None:
        latest_run_ids = session.scalars(
            select(AnalysisRunRecord.id).where(
                AnalysisRunRecord.monitoring_case_id == case.id,
                AnalysisRunRecord.started_at == latest_started_at,
            )
        ).all()
        latest_claim_ids = session.scalars(
            select(VerdictRecord.claim_id).where(
                VerdictRecord.run_id.in_(latest_run_ids)
            )
        ).all()
        claim_ids = list(dict.fromkeys(latest_claim_ids))
    else:
        claim_ids = list(
            session.scalars(
                select(Claim.id).where(Claim.report_id == case.report_id)
            ).all()
        )
    return {
        "id": case.id,
        "company_id": case.company_id,
        "company_name": company.legal_name if company else None,
        "report_id": case.report_id,
        "report_title": report.title if report else None,
        "case_type": case.case_type,
        "next_review_date": case.next_review_date,
        "importance": case.importance,
        "monitoring_data_synthetic": case.monitoring_data_synthetic,
        # fixture:// 보고서는 보고서와 공개 데이터까지 합성한 C 사례다.
        # A·B의 실제 기업 공개자료와 데모용 여신관리 정보를 구분한다.
        "evidence_data_synthetic": bool(
            report and report.source_url.startswith("fixture://")
        ),
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


def _analyze_live_case(
    case_data: dict,
    *,
    allow_cache_fallback: bool,
) -> tuple[CaseAnalysis, dict]:
    report = ReportContract.model_validate(case_data["report"])
    pdf_name = REPORT_PDF_BY_ID.get(report.id)
    if pdf_name is None:
        raise HTTPException(
            status_code=422,
            detail="이 사례에는 Gemini live 실행용 원본 PDF가 없습니다",
        )
    pdf_path = REFERENCES_DIR / pdf_name
    if not pdf_path.exists():
        raise HTTPException(
            status_code=503,
            detail=f"Gemini live 실행용 PDF를 찾을 수 없습니다: {pdf_name}",
        )
    try:
        client = GeminiStructuredClaimClient()
    except GeminiConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    cache = (
        VerifiedClaimCache.from_fixture_directory(FIXTURES_DIR)
        if allow_cache_fallback
        else VerifiedClaimCache()
    )
    pages = list(
        LIVE_EXTRACTION_PAGES_BY_REPORT.get(
            report.id,
            tuple(sorted({int(claim["page"]) for claim in case_data["claims"]})),
        )
    )

    def extract_page(page: int):
        return extract_document_page(
            run_id=f"ui-live-{report.id}-{page}",
            pdf_path=pdf_path,
            report=report,
            page=page,
            mode=ExecutionMode.LIVE,
            cache=cache,
            client=client,
            model_name=client.model_name,
            prompt_version=client.prompt_version,
        )

    # 사례 A처럼 근거 페이지가 여러 장이면 순차 실행 시
    # (페이지 수 × 2회 재시도 × Gemini timeout)만큼 UI 제한시간을 넘길 수
    # 있다. 페이지는 서로 독립적이므로 동시에 추출하고, 결과는 다시 페이지
    # 순서로 정렬해 이후 결정론적 파이프라인의 재현성을 유지한다.
    with ThreadPoolExecutor(max_workers=min(len(pages), 3)) as executor:
        runs_by_page = dict(zip(pages, executor.map(extract_page, pages), strict=True))

    extraction_results = []
    attempts = 0
    fallback_reasons: list[str] = []
    for page in pages:
        run = runs_by_page[page]
        if run.state is RunState.FAILED or run.result is None:
            raise HTTPException(
                status_code=502,
                detail=f"Gemini live 추출 실패(p.{page}): {run.error}",
            )
        extraction_results.append(run.result)
        attempts += run.result.attempts
        if run.result.failure_reason:
            fallback_reasons.append(
                f"p.{page}: {run.result.failure_reason}"
            )

    extractions = tuple(extraction_results)
    case_analysis = analyze_case_extractions(
        case_data,
        extractions=extractions,
        skip_unmatched_claims=True,
    )
    matched_claim_ids = {
        claim_id
        for claim_id, _ in _map_runs_to_claim_and_fact(case_analysis).values()
    }
    extracted_claims = [
        claim for result in extractions for claim in result.claims
    ]
    skipped_claims = [
        {
            "id": claim.id,
            "page": claim.page,
            "metric": claim.metric,
            "scope": claim.scope.value if claim.scope else None,
            "reason": "대응하는 공개 데이터 없음",
        }
        for claim in extracted_claims
        if claim.id not in matched_claim_ids
    ]
    modes = {result.execution_mode for result in extractions}
    execution_mode = (
        ExecutionMode.LIVE
        if modes == {ExecutionMode.LIVE}
        else ExecutionMode.FALLBACK
    )
    return case_analysis, {
        "requested_mode": "live",
        "execution_mode": execution_mode.value,
        "model": client.model_name,
        "pages": pages,
        "attempts": attempts,
        "fallback_reasons": fallback_reasons,
        "skipped_claims": skipped_claims,
        "extracted_claim_count": len(extracted_claims),
        "compared_claim_count": len(matched_claim_ids),
    }


@router.post("/{case_id}/analyze")
def analyze_case(
    case_id: str,
    request: AnalyzeCaseRequest | None = None,
    session: Session = Depends(get_session),
) -> dict:
    """demo 캐시 또는 실제 Gemini structured output으로 분석을 실행한다."""

    case = session.get(MonitoringCaseRecord, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="사례를 찾을 수 없습니다")

    case_data = _find_case_fixture(case_id)
    options = request or AnalyzeCaseRequest()

    with case_analysis_lock(case_id):
        if options.mode == "live":
            case_analysis, execution = _analyze_live_case(
                case_data,
                allow_cache_fallback=options.allow_cache_fallback,
            )
        else:
            cache = VerifiedClaimCache.from_fixture_directory(FIXTURES_DIR)
            case_analysis = analyze_verified_case(case_data, cache=cache)
            execution = {
                "requested_mode": "demo",
                "execution_mode": ExecutionMode.VERIFIED_CACHE.value,
                "model": None,
                "pages": sorted(
                    {int(claim["page"]) for claim in case_data["claims"]}
                ),
                "attempts": 0,
                "fallback_reasons": [],
                "skipped_claims": [],
                "extracted_claim_count": sum(
                    len(extraction.claims)
                    for extraction in case_analysis.extractions
                ),
                "compared_claim_count": 0,
            }
        claim_and_fact_ids_by_run = _map_runs_to_claim_and_fact(case_analysis)
        if options.mode == "demo":
            execution["compared_claim_count"] = len(
                {
                    claim_id
                    for claim_id, _ in claim_and_fact_ids_by_run.values()
                }
            )
        persist_case_analysis(
            session,
            case_analysis,
            claim_and_fact_ids_by_run=claim_and_fact_ids_by_run,
        )

    return {
        "case": _case_summary(session, case),
        "execution": execution,
    }
