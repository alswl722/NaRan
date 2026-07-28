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

        result = extract_claims(
            document_hash=document.file_hash,
            report_id=report.id,
            page=page,
            candidate_texts=tuple(
                candidate.raw_text for candidate in filtered.candidates
            ),
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
