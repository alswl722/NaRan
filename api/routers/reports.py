"""보고서 원본 PDF 서빙.

GET /reports/{id}/pdf                     PDF 바이너리 (Range 지원)
GET /reports/{id}/pdf/meta                실물 파일 존재 여부
GET /reports/{id}/pdf/highlight?claim_id  claim 값의 PDF 내 좌표(있으면)

report_id -> references/ 실물 파일 매핑은 정적 테이블로 관리한다.
source_url은 원본 발행처 URL이라 실제 로컬 파일명과 형식이 사례마다
달라(A는 쿼리 파라미터, B는 경로) 파싱 규칙으로 신뢰할 수 없다. 정적
테이블이 가장 명시적이고, 새 사례 추가 시 실패가 파싱 실패가 아니라
"매핑 없음" 404로 드러난다.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from db.models import Claim as ClaimRecord, Report as ReportRecord
from db.parser import find_value_bbox
from db.session import get_session

router = APIRouter(prefix="/reports", tags=["reports"])

REFERENCES_DIR = Path(__file__).resolve().parents[2] / "references"

REPORT_ID_TO_FILENAME: dict[str, str] = {
    "report-a-2024": "Samsung-Biologics-2025-ESG-Report_KR.pdf",
    "report-b-2024": "Samsung_Electronics_Sustainability_Report_2025_ENG.pdf",
    # report-c-2024: 의도적으로 없음 — 합성 사례, 실물 PDF 없음
}


def _get_report_or_404(session: Session, report_id: str) -> ReportRecord:
    report = session.get(ReportRecord, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="보고서를 찾을 수 없습니다")
    return report


def _resolve_pdf_path(report: ReportRecord) -> Path:
    """파일을 찾고 report.file_hash와 실제 내용의 해시가 일치하는지 검증한다.

    api/agent/document_extract.py의 file_hash 검증 습관을 그대로 따른다 —
    매핑 테이블이 잘못됐거나 references/ 파일이 나중에 바뀌었을 때 조용히
    다른 문서를 서빙하지 않기 위함이다.
    """
    filename = REPORT_ID_TO_FILENAME.get(report.id)
    if filename is None:
        raise HTTPException(
            status_code=404,
            detail="이 보고서는 원본 PDF 실물 파일이 없습니다 (합성 사례일 수 있음)",
        )
    path = REFERENCES_DIR / filename
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"매핑된 PDF 파일을 찾을 수 없습니다: {filename}",
        )
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    actual_hash = f"sha256:{digest.hexdigest()}"
    if actual_hash != report.file_hash:
        raise HTTPException(
            status_code=500,
            detail="PDF 파일 해시가 Report.file_hash와 일치하지 않습니다 — 서빙을 중단합니다",
        )
    return path


@router.get("/{report_id}/pdf")
def get_report_pdf(
    report_id: str, session: Session = Depends(get_session)
) -> FileResponse:
    report = _get_report_or_404(session, report_id)
    path = _resolve_pdf_path(report)
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=REPORT_ID_TO_FILENAME[report_id],
    )


@router.get("/{report_id}/pdf/meta")
def get_report_pdf_meta(
    report_id: str, session: Session = Depends(get_session)
) -> dict:
    report = _get_report_or_404(session, report_id)
    filename = REPORT_ID_TO_FILENAME.get(report.id)
    if filename is None or not (REFERENCES_DIR / filename).is_file():
        return {"available": False}
    return {"available": True, "filename": filename}


@router.get("/{report_id}/pdf/highlight")
def get_report_pdf_highlight(
    report_id: str, claim_id: str, session: Session = Depends(get_session)
) -> dict:
    """claim.value의 PDF 내 좌표를 찾는다. 못 찾으면 found=false를 반환한다
    (실패를 숨기지 않되, 페이지 자동 이동 자체는 여전히 동작해야 하므로
    404가 아니라 200 + found=false로 응답한다).

    claim.raw_text 전체가 아니라 claim.value(숫자)만 찾는 이유는
    db.parser.find_value_bbox의 docstring 참고 — fixture의 raw_text는
    PDF 원문 그대로가 아니라 사람이 표를 보고 요약한 문장이라 문장 단위
    매칭은 원리적으로 실패한다.
    """
    report = _get_report_or_404(session, report_id)
    path = _resolve_pdf_path(report)

    claim = session.get(ClaimRecord, claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail="주장을 찾을 수 없습니다")
    if claim.report_id != report.id:
        raise HTTPException(
            status_code=400, detail="claim이 이 보고서에 속하지 않습니다"
        )
    if claim.value is None:
        return {"found": False}

    bbox = find_value_bbox(path, page=claim.page, value=str(claim.value))
    if bbox is None:
        return {"found": False}
    return {
        "found": True,
        "page": claim.page,
        "x0": bbox.x0,
        "top": bbox.top,
        "x1": bbox.x1,
        "bottom": bbox.bottom,
        "page_width": bbox.page_width,
        "page_height": bbox.page_height,
    }
