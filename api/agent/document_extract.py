"""PDF 파싱부터 Claim 구조화까지의 추출 실행과 트레이스."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from api.agent.llm_extract import (
    DEFAULT_MODEL,
    DEFAULT_PROMPT_VERSION,
    DEFAULT_SCHEMA_VERSION,
    ExtractionResult,
    StructuredClaimClient,
    VerifiedClaimCache,
    extract_claims,
)
from api.agent.orchestrator import DEFAULT_RUN_LOCK, RunLock, RunState
from db.parser import parse_pdf, prefilter_claim_candidates
from naran.contracts import (
    ExecutionMode,
    Report,
    TraceEvent,
    TraceStepType,
)


@dataclass(frozen=True)
class DocumentExtractionRun:
    run_id: str
    state: RunState
    result: ExtractionResult | None
    trace: tuple[TraceEvent, ...]
    error: str | None = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _event(
    *,
    step_type: TraceStepType,
    stage: str,
    summary: str,
    clock: Callable[[], datetime],
    tool_name: str | None = None,
    evidence: list[str] | None = None,
) -> TraceEvent:
    return TraceEvent(
        step_type=step_type,
        stage=stage,
        tool_name=tool_name,
        input_summary=summary,
        evidence=evidence or [],
        created_at=clock(),
    )


def extract_document_page(
    *,
    run_id: str,
    pdf_path: str | Path,
    report: Report,
    page: int,
    mode: ExecutionMode,
    cache: VerifiedClaimCache,
    client: StructuredClaimClient | None = None,
    model_name: str = DEFAULT_MODEL,
    prompt_version: str = DEFAULT_PROMPT_VERSION,
    schema_version: str = DEFAULT_SCHEMA_VERSION,
    table_context_label: str | None = None,
    run_lock: RunLock = DEFAULT_RUN_LOCK,
    clock: Callable[[], datetime] = _utc_now,
) -> DocumentExtractionRun:
    """한 PDF 페이지를 추출하고 실패와 fallback을 모두 기록한다."""

    trace: list[TraceEvent] = []
    run_lock.acquire(run_id)
    try:
        trace.append(
            _event(
                step_type=TraceStepType.PLAN,
                stage="문서 추출 계획",
                summary="PDF 원문 확인 → 주장 후보 필터 → 구조화 Claim 검증",
                clock=clock,
            )
        )
        document = parse_pdf(pdf_path, pages={page})
        if document.file_hash != report.file_hash:
            raise ValueError("PDF 해시가 Report.file_hash와 일치하지 않습니다")
        page_content = document.pages[0]
        trace.append(
            _event(
                step_type=TraceStepType.OBSERVATION,
                stage="PDF 페이지 추출",
                summary=(
                    f"page={page}; text_layer={page_content.has_text_layer}; "
                    f"tables={len(page_content.tables)}"
                ),
                clock=clock,
                tool_name="pdf.parse",
                evidence=[
                    document.file_hash,
                    *page_content.extraction_errors,
                ],
            )
        )
        filtered = prefilter_claim_candidates(document)
        trace.append(
            _event(
                step_type=TraceStepType.OBSERVATION,
                stage="주장 후보 필터",
                summary=(
                    f"included={filtered.included_count}; "
                    f"excluded={filtered.excluded_count}"
                ),
                clock=clock,
                tool_name="claim.prefilter",
                evidence=[
                    f"page:{candidate.page}:line:{candidate.line}"
                    for candidate in filtered.candidates
                ],
            )
        )
        if page in filtered.pages_without_text:
            raise ValueError("선택한 PDF 페이지에 텍스트 레이어가 없습니다")

        candidate_texts = [
            candidate.raw_text for candidate in filtered.candidates
        ]
        if table_context_label:
            # 복잡한 양단 표는 Scope 제목과 국내 사업장 수치가 서로 다른
            # 텍스트 조각으로 추출된다. 표를 좌·우 반으로 나눈 뒤 국내
            # 사업장 행에 화면상 상위 제목을 붙여 Gemini에 문맥을 보존한다.
            # 값은 코드에 저장하지 않고 매 실행마다 PDF 표에서 읽는다.
            contextual_rows: list[str] = []
            for table in page_content.tables:
                method_by_half: list[str | None] = [None, None]
                for row in table.rows:
                    midpoint = max(1, len(row) // 2)
                    # 중앙 구분선 주변의 연도 값 열이 페이지마다 1~2칸
                    # 다르므로 왼쪽 조각을 조금 겹쳐 잘라 최신연도 값을
                    # 잃지 않는다.
                    left_end = min(len(row), (len(row) + 1) // 2 + 2)
                    for half_index, segment in enumerate(
                        (row[:left_end], row[midpoint:])
                    ):
                        cells = [
                            cell.replace("\n", " ").strip()
                            for cell in segment
                            if cell.strip()
                        ]
                        joined = " ".join(cells)
                        compact_joined = joined.replace(" ", "").casefold()
                        if "location-based" in compact_joined:
                            method_by_half[half_index] = "지역기반"
                        elif "market-based" in compact_joined:
                            method_by_half[half_index] = "시장기반"
                        elif "배출권거래제" in compact_joined:
                            method_by_half[half_index] = "배출권거래제 기준"
                        domestic_at = joined.find("국내 사업")
                        if domestic_at < 0:
                            continue
                        domestic_row = joined[domestic_at:]
                        if "tCO" not in domestic_row or not any(
                            char.isdigit() for char in domestic_row
                        ):
                            continue
                        method_context = method_by_half[half_index]
                        full_context = (
                            f"{table_context_label} · {method_context}"
                            if method_context
                            else table_context_label
                        )
                        contextual_rows.append(
                            f"[표 문맥: {full_context}] {domestic_row}"
                        )
            candidate_texts.extend(dict.fromkeys(contextual_rows))

        result = extract_claims(
            document_hash=document.file_hash,
            report_id=report.id,
            page=page,
            candidate_texts=tuple(candidate_texts),
            mode=mode,
            cache=cache,
            client=client,
            model_name=model_name,
            prompt_version=prompt_version,
            schema_version=schema_version,
        )
        trace.append(
            _event(
                step_type=TraceStepType.ACTION,
                stage="Claim 구조화",
                summary=(
                    f"mode={result.execution_mode}; claims={len(result.claims)}; "
                    f"attempts={result.attempts}"
                ),
                clock=clock,
                tool_name="claim.extract",
                evidence=[
                    result.cache_key.digest,
                    *(
                        [result.failure_reason]
                        if result.failure_reason is not None
                        else []
                    ),
                ],
            )
        )
        return DocumentExtractionRun(
            run_id=run_id,
            state=RunState.COMPLETED,
            result=result,
            trace=tuple(trace),
        )
    except Exception as exc:
        trace.append(
            _event(
                step_type=TraceStepType.ACTION,
                stage="문서 추출 실패",
                summary=f"{type(exc).__name__}: {exc}",
                clock=clock,
                tool_name="run.fail",
            )
        )
        return DocumentExtractionRun(
            run_id=run_id,
            state=RunState.FAILED,
            result=None,
            trace=tuple(trace),
            error=f"{type(exc).__name__}: {exc}",
        )
    finally:
        run_lock.release(run_id)
