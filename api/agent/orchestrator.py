"""규칙 엔진을 우회하지 않는 분석 오케스트레이터와 트레이스."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from threading import Lock
from typing import Callable

from db.compare_engine import (
    ComparisonOutcome,
    compare_performance,
)
from db.entity_map import EntityMapping
from naran.contracts import (
    Claim,
    ExecutionMode,
    PublicFact,
    Report,
    TraceEvent,
    TraceStepType,
)

from api.agent.review_difference import (
    DifferenceFinding,
    assess_difference_findings,
)


class RunState(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RunAlreadyActiveError(RuntimeError):
    """같은 실행 ID가 이미 처리 중일 때 발생한다."""


@dataclass(frozen=True)
class AnalysisRun:
    run_id: str
    state: RunState
    outcome: ComparisonOutcome | None
    trace: tuple[TraceEvent, ...]
    error: str | None = None


class RunLock:
    """프로세스 안에서 동일 run_id의 중복 실행을 막는다."""

    def __init__(self) -> None:
        self._guard = Lock()
        self._active: set[str] = set()

    def acquire(self, run_id: str) -> None:
        with self._guard:
            if run_id in self._active:
                raise RunAlreadyActiveError(f"이미 실행 중인 run_id입니다: {run_id}")
            self._active.add(run_id)

    def release(self, run_id: str) -> None:
        with self._guard:
            self._active.discard(run_id)


DEFAULT_RUN_LOCK = RunLock()


class _Trace:
    def __init__(self, clock: Callable[[], datetime]) -> None:
        self._clock = clock
        self.events: list[TraceEvent] = []

    def add(
        self,
        step_type: TraceStepType,
        stage: str,
        summary: str,
        *,
        tool_name: str | None = None,
        evidence: list[str] | None = None,
    ) -> None:
        self.events.append(
            TraceEvent(
                step_type=step_type,
                stage=stage,
                tool_name=tool_name,
                input_summary=summary,
                evidence=evidence or [],
                created_at=self._clock(),
            )
        )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def analyze_performance(
    *,
    run_id: str,
    report: Report,
    claim: Claim,
    public_fact: PublicFact,
    boundary_mapping: EntityMapping | None = None,
    difference_findings: list[DifferenceFinding] | None = None,
    public_data_mode: ExecutionMode = ExecutionMode.VERIFIED_CACHE,
    fallback_reason: str | None = None,
    run_lock: RunLock = DEFAULT_RUN_LOCK,
    clock: Callable[[], datetime] = _utc_now,
) -> AnalysisRun:
    """실적주장을 비교하고 동일 흐름의 감사 가능한 트레이스를 반환한다."""

    trace = _Trace(clock)
    run_lock.acquire(run_id)
    try:
        if public_data_mode is ExecutionMode.FALLBACK:
            if not fallback_reason or not fallback_reason.strip():
                raise ValueError("fallback 모드에는 실패 원인이 필요합니다")
        elif fallback_reason is not None:
            raise ValueError("fallback이 아닌 실행에는 fallback_reason을 지정할 수 없습니다")
        trace.add(
            TraceStepType.PLAN,
            "분석 계획",
            "주장 근거 확인 → 공개 데이터 확인 → 비교 가능성 검사 → 조건부 수치 대조",
        )
        trace.add(
            TraceStepType.OBSERVATION,
            "주장 추출 결과",
            f"{claim.claim_type} · {claim.metric} · 원문 p.{claim.page}",
            tool_name="claim.verified_input",
            evidence=[
                f"{report.source_url}#page={claim.page}",
                report.file_hash,
            ],
        )
        trace.add(
            TraceStepType.ACTION,
            "공개 데이터 조회",
            f"mode={public_data_mode}; 공개 데이터 {public_fact.version} 사용",
            tool_name="public_data.snapshot",
            evidence=[
                public_fact.source_url,
                public_fact.source_hash,
                public_fact.retrieved_at.isoformat(),
                *([fallback_reason] if fallback_reason is not None else []),
            ],
        )

        difference_assessment = assess_difference_findings(
            difference_findings or []
        )
        outcome = compare_performance(
            claim,
            public_fact,
            boundary_mapping=boundary_mapping,
            claim_company_id=report.company_id,
            difference_evidence=difference_assessment.evidence,
            evidence_note=difference_assessment.note,
            evidence_source=difference_assessment.source,
        )
        comparability = outcome.comparability
        condition_summary = ", ".join(
            f"{condition.field}={condition.status}" for condition in comparability.conditions
        )
        trace.add(
            TraceStepType.OBSERVATION,
            "비교 가능성 검사",
            f"comparable={comparability.comparable}; {condition_summary}",
            tool_name="comparability.check",
            evidence=[
                *comparability.missing_fields,
                *comparability.mismatch_reasons,
            ],
        )

        if not comparability.comparable:
            trace.add(
                TraceStepType.ACTION,
                "계산 중단",
                outcome.verdict.explanation,
                tool_name="compare.stop",
                evidence=outcome.verdict.review_reasons,
            )
        else:
            trace.add(
                TraceStepType.ACTION,
                "수치 대조",
                (
                    f"status={outcome.verdict.status}; "
                    f"match_type={outcome.verdict.match_type}"
                ),
                tool_name="compare.performance",
                evidence=[outcome.verdict.explanation],
            )
            if outcome.verdict.match_type == "different":
                trace.add(
                    TraceStepType.OBSERVATION,
                    "차이 원인 재검토",
                    f"근거 수준={difference_assessment.evidence}",
                    tool_name="difference.review",
                    evidence=[
                        value
                        for value in (
                            difference_assessment.note,
                            difference_assessment.source,
                        )
                        if value is not None
                    ],
                )

        route = (
            "담당자 검토 대기열로 전달"
            if outcome.verdict.review_required
            else "자동 분석 완료"
        )
        trace.add(
            TraceStepType.ACTION,
            "HITL 라우팅",
            route,
            tool_name="review.route",
            evidence=outcome.verdict.review_reasons,
        )
        return AnalysisRun(
            run_id=run_id,
            state=RunState.COMPLETED,
            outcome=outcome,
            trace=tuple(trace.events),
        )
    except Exception as exc:  # 실행 실패를 성공으로 숨기지 않고 결과에 보존한다.
        trace.add(
            TraceStepType.ACTION,
            "분석 실패",
            f"{type(exc).__name__}: {exc}",
            tool_name="run.fail",
        )
        return AnalysisRun(
            run_id=run_id,
            state=RunState.FAILED,
            outcome=None,
            trace=tuple(trace.events),
            error=f"{type(exc).__name__}: {exc}",
        )
    finally:
        run_lock.release(run_id)
