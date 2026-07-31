"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useRef, useState } from "react";
import { ANALYZE_TIMEOUT_MS, apiGet, apiPost, ApiError } from "@/lib/api";
import type {
  AnalyzeExecution,
  AnalysisProgress,
  AnalyzeResponse,
  CaseSummary,
  ClaimDetail,
  ReportPdfMeta,
  ReviewItem,
  ReviewItemHistoryRecord,
  ReviewRecord,
  RunSummary,
  TraceEvent,
} from "@/lib/types";
import { ClaimCard } from "@/components/ClaimCard";
import { AnalysisProgressPanel } from "@/components/AnalysisProgressPanel";
import { HitlPanel } from "@/components/HitlPanel";
import { PdfPanel } from "@/components/PdfPanel";
import { reviewReasonLabel } from "@/lib/labels";

type RunWithTrace = { run: RunSummary; trace: TraceEvent[] };

export default function CaseDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: caseId } = use(params);

  const [caseSummary, setCaseSummary] = useState<CaseSummary | null>(null);
  const [claimDetails, setClaimDetails] = useState<ClaimDetail[]>([]);
  const [runsWithTrace, setRunsWithTrace] = useState<RunWithTrace[]>([]);
  const [reviewHistory, setReviewHistory] = useState<ReviewRecord[]>([]);
  const [reviewItemHistory, setReviewItemHistory] = useState<ReviewItemHistoryRecord[]>([]);
  const [pdfAvailable, setPdfAvailable] = useState(false);
  const [activeClaimId, setActiveClaimId] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisMode, setAnalysisMode] = useState<"demo" | "live">("demo");
  const [lastExecution, setLastExecution] = useState<AnalyzeExecution | null>(null);
  const [analysisProgress, setAnalysisProgress] = useState<AnalysisProgress | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const claimListRef = useRef<HTMLElement | null>(null);
  const claimCardRefs = useRef(new Map<string, HTMLDivElement>());

  const loadAll = useCallback(async () => {
    const summary = await apiGet<CaseSummary>(`/cases/${caseId}`);
    setCaseSummary(summary);

    const claims = await Promise.all(
      summary.claim_ids.map((cid) => apiGet<ClaimDetail>(`/claims/${cid}`)),
    );
    setClaimDetails(claims);

    // 원문 PDF 열람 가능 여부는 사례당 한 번만 조회해 각 ClaimCard에 내려준다
    // — 카드마다 반복 조회하지 않기 위함. 실패해도 페이지 전체가 깨지지
    // 않도록 폴백한다(분석 결과 자체의 실패가 아니라 부가 기능 가용성 체크).
    const pdfMeta = await apiGet<ReportPdfMeta>(
      `/reports/${summary.report_id}/pdf/meta`,
    ).catch(() => ({ available: false }) as ReportPdfMeta);
    setPdfAvailable(pdfMeta.available);

    const runs = await apiGet<RunSummary[]>(`/cases/${caseId}/runs`);
    const withTrace = await Promise.all(
      runs.map(async (run) => ({
        run,
        trace: await apiGet<TraceEvent[]>(`/runs/${run.id}/trace`),
      })),
    );
    setRunsWithTrace(withTrace);

    const history = await apiGet<ReviewRecord[]>(`/reviews/${caseId}/history`).catch(
      () => [] as ReviewRecord[],
    );
    setReviewHistory(history);
    const itemHistory = await apiGet<ReviewItemHistoryRecord[]>(
      `/reviews/${caseId}/items`,
    ).catch(() => [] as ReviewItemHistoryRecord[]);
    setReviewItemHistory(itemHistory);
  }, [caseId]);

  useEffect(() => {
    let alive = true;
    async function run() {
      try {
        await loadAll();
        if (alive) setLoadError(null);
      } catch (err) {
        if (alive) {
          setLoadError(err instanceof ApiError ? err.message : "사례를 불러오지 못했습니다");
        }
      }
    }
    void run();
    return () => {
      alive = false;
    };
  }, [loadAll]);

  useEffect(() => {
    if (!analyzing) return;
    let alive = true;

    async function pollProgress() {
      const progress = await apiGet<AnalysisProgress>(
        `/cases/${caseId}/analyze/progress`,
      ).catch(() => null);
      if (alive && progress?.status !== "idle") {
        setAnalysisProgress(progress);
      }
    }

    void pollProgress();
    const interval = window.setInterval(pollProgress, 600);
    return () => {
      alive = false;
      window.clearInterval(interval);
    };
  }, [analyzing, caseId]);

  // 좌측 PdfPanel에 보여줄 claim — 사용자가 고른 선택(activeClaimId)이
  // 현재 목록에 없으면(최초 로드, 재분석 후 claim 구성 변경 등) 첫 번째로
  // 대체한다. effect로 state를 동기화하지 않고 렌더 시점에 파생시킨다.
  const effectiveClaimId =
    activeClaimId && claimDetails.some((d) => d.claim.id === activeClaimId)
      ? activeClaimId
      : (claimDetails[0]?.claim.id ?? null);

  function selectClaimFromNavigator(claimId: string) {
    setActiveClaimId(claimId);
    window.requestAnimationFrame(() => {
      const container = claimListRef.current;
      const card = claimCardRefs.current.get(claimId);
      if (!container || !card) return;

      // 데스크톱에서는 우측 카드 목록만 스크롤하고, 목록 자체가 스크롤되지
      // 않는 작은 화면에서는 페이지가 해당 카드로 이동하게 한다.
      if (container.scrollHeight > container.clientHeight) {
        const top =
          container.scrollTop +
          card.getBoundingClientRect().top -
          container.getBoundingClientRect().top;
        container.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
      } else {
        card.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
  }

  async function runAnalysis() {
    setAnalyzing(true);
    setAnalysisProgress(null);
    setAnalysisError(null);
    try {
      const response = await apiPost<AnalyzeResponse>(
        `/cases/${caseId}/analyze`,
        {
          mode: analysisMode,
          allow_cache_fallback: false,
        },
        ANALYZE_TIMEOUT_MS,
      );
      setLastExecution(response.execution);
      const finalProgress = await apiGet<AnalysisProgress>(
        `/cases/${caseId}/analyze/progress`,
      ).catch(() => null);
      if (finalProgress) setAnalysisProgress(finalProgress);
      await loadAll();
    } catch (err) {
      setAnalysisError(
        err instanceof ApiError ? err.message : "분석 실행에 실패했습니다. 잠시 후 다시 시도해 주세요.",
      );
    } finally {
      setAnalyzing(false);
    }
  }

  if (loadError && !caseSummary) {
    return (
      <div className="w-full px-8 py-8 lg:px-12">
        <p className="text-[15.5px] text-status-unexplained">{loadError}</p>
        <Link href="/cases" className="mt-4 inline-block text-[14.5px] text-brand underline">
          대기열로 돌아가기
        </Link>
      </div>
    );
  }

  if (!caseSummary) {
    return (
      <div className="w-full px-8 py-8 text-[15.5px] text-faint lg:px-12">불러오는 중…</div>
    );
  }

  const analyzed = caseSummary.review_required !== null;
  const notComparableClaims = claimDetails.filter((d) =>
    d.comparisons.some((c) => c.verdict.status === "비교 불가"),
  );
  const followUpQuestion =
    lastExecution?.requested_mode === "live" &&
    lastExecution.compared_claim_count === 0
      ? null
      : (claimDetails
          .flatMap((d) =>
            d.comparisons.map((c) => {
              const hasPendingReason = c.verdict.review_reasons.some(
                (reason) =>
                  c.verdict.review_resolutions[reason]?.resolution !== "확인 완료",
              );
              return hasPendingReason ? c.verdict.follow_up_question : null;
            }),
          )
          .find((q) => q !== null) ?? null);
  const reviewItems: ReviewItem[] = claimDetails.flatMap((detail) =>
    detail.comparisons.flatMap((comparison) =>
      comparison.verdict.review_required
        ? comparison.verdict.review_reasons.map((reason) => ({
            verdict_id: comparison.verdict.id,
            claim_id: detail.claim.id,
            scope: detail.claim.scope ?? detail.claim.metric,
            reason,
            reason_label: reviewReasonLabel(reason),
            resolution: comparison.verdict.review_resolutions[reason] ?? null,
          }))
        : [],
    ),
  );

  return (
    <div className="w-full flex-1 px-8 py-8 lg:px-12">
      <Link href="/cases" className="text-[14.5px] text-faint hover:text-ink">
        ← 대기열로
      </Link>

      <header className="mt-3 mb-6 grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(360px,520px)]">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-bold text-ink-strong">
              {caseSummary.company_name ?? caseSummary.company_id}
            </h1>
            {caseSummary.monitoring_data_synthetic && (
              <span className="rounded-full bg-muted/15 px-2.5 py-1 text-[13.5px] font-medium text-muted">
                {caseSummary.evidence_data_synthetic
                  ? "완전 합성 사례"
                  : "실제 공개자료 · 여신정보 데모"}
              </span>
            )}
          </div>
          <p className="mt-1 text-[15.5px] text-muted">
            {caseSummary.report_title} · {caseSummary.case_type}
          </p>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <div className="flex rounded-sm border border-line bg-white p-1">
            <button
              type="button"
              onClick={() => setAnalysisMode("demo")}
              disabled={analyzing}
              className={`rounded-sm px-3 py-1.5 text-[14px] font-semibold ${
                analysisMode === "demo" ? "bg-ink-strong text-white" : "text-muted"
              }`}
            >
              검증 저장값
            </button>
            <button
              type="button"
              onClick={() => setAnalysisMode("live")}
              disabled={analyzing}
              className={`rounded-sm px-3 py-1.5 text-[14px] font-semibold ${
                analysisMode === "live" ? "bg-brand text-ink-strong" : "text-muted"
              }`}
            >
              Gemini 실시간
            </button>
          </div>
          <button
            type="button"
            onClick={runAnalysis}
            disabled={analyzing}
            className="rounded-sm bg-brand px-5 py-2.5 text-[15.5px] font-semibold text-ink-strong shadow-card disabled:cursor-not-allowed disabled:opacity-60"
          >
            {analyzing
              ? analysisMode === "live"
                ? "Gemini 분석 중…"
                : "분석 실행 중…"
              : analyzed
                ? "다시 분석 실행"
                : "분석 시작"}
          </button>
        </div>
        {lastExecution && (
          <div
            className={`mt-3 rounded-sm border px-4 py-3 text-[14px] ${
              lastExecution.execution_mode === "live"
                ? "border-emerald-300 bg-emerald-50 text-emerald-900"
                : lastExecution.execution_mode === "fallback"
                  ? "border-amber-300 bg-amber-50 text-amber-900"
                  : "border-line bg-white text-muted"
            }`}
          >
            <span className="font-bold">
              {lastExecution.execution_mode === "live"
                ? "Gemini 실시간 분석 완료"
                : lastExecution.execution_mode === "fallback"
                  ? "실시간 분석 실패 · 검증값 사용"
                  : "검증 저장값으로 분석 완료"}
            </span>
            <span className="ml-2">
              {lastExecution.model ? `${lastExecution.model} · ` : ""}
              p.{lastExecution.pages.join(", ")} · 시도 {lastExecution.attempts}회
            </span>
            <p className="mt-1">
              추출 {lastExecution.extracted_claim_count}건 · 공개 데이터 대조{" "}
              {lastExecution.compared_claim_count}건
            </p>
            {lastExecution.fallback_reasons.length > 0 && (
              <p className="mt-1 break-words">
                {lastExecution.fallback_reasons.join(" | ")}
              </p>
            )}
            {lastExecution.skipped_claims.length > 0 && (
              <div className="mt-1">
                <p>
                  공개 데이터와 자동 매칭되지 않은 주장{" "}
                  {lastExecution.skipped_claims.length}건
                </p>
                <ul className="mt-0.5 list-disc pl-5 text-[13px]">
                  {lastExecution.skipped_claims.map((claim) => (
                    <li key={claim.id}>
                      p.{claim.page} · {claim.scope ?? "Scope 미확인"} · {claim.metric}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
        {analysisError && (
          <p className="mt-2 text-[14.5px] text-status-unexplained">{analysisError}</p>
        )}
        {loadError && (
          <p className="mt-2 text-[14.5px] text-status-unexplained">
            최신 사례 정보를 새로고침하지 못했습니다. 현재 표시된 결과는 이전 조회 내용입니다.
          </p>
        )}
        </div>
        {analysisProgress && (
          <AnalysisProgressPanel progress={analysisProgress} />
        )}
      </header>

      {/* 장면 2 — 비교 불가 사례는 계산 중단 사실을 가장 먼저 강조한다 */}
      {notComparableClaims.length > 0 && (
        <div className="mb-6 flex items-start gap-2.5 rounded-sm bg-brand-soft p-5">
          <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand" />
          <div>
            <h2 className="text-[15.5px] font-bold text-ink-strong">계산이 중단되었습니다</h2>
            <p className="mt-1 text-[14.5px] text-ink">
              보고서 값과 공개 데이터의 조직·지역 범위가 달라 차이를 계산하지 않았습니다. 동일한
              범위의 자료를 요청해 주세요.
            </p>
          </div>
        </div>
      )}

      {/* 좌우 고정 분할 — "나란히" 컨셉의 핵심 뷰. 좌측 PdfPanel은 원문을
          상시 보여주고(lg 이상에서 sticky), 우측 카드를 고르면 좌측이 그
          claim의 페이지·좌표로 동기화된다. */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <PdfPanel
          activeDetail={claimDetails.find((d) => d.claim.id === effectiveClaimId)}
          pdfAvailable={pdfAvailable}
          claimDetails={claimDetails}
          activeClaimId={effectiveClaimId}
          onSelectClaim={selectClaimFromNavigator}
        />
        <section
          ref={claimListRef}
          data-testid="claim-list"
          className="flex flex-col gap-4 lg:max-h-[calc(100vh-4rem)] lg:overflow-y-auto"
        >
          {claimDetails.map((detail) => (
            <div
              key={detail.claim.id}
              data-testid={`claim-card-${detail.claim.id}`}
              ref={(element) => {
                if (element) claimCardRefs.current.set(detail.claim.id, element);
                else claimCardRefs.current.delete(detail.claim.id);
              }}
            >
              <ClaimCard
                detail={detail}
                runs={runsWithTrace.filter(({ run }) =>
                  run.logical_key.includes(`-${detail.claim.id}-`),
                )}
                isActive={detail.claim.id === effectiveClaimId}
                onSelect={() => setActiveClaimId(detail.claim.id)}
              />
            </div>
          ))}
        </section>
      </div>

      {/* 담당자 검토 — claim 카드들 아래, 전체 폭으로 배치한다. */}
      <section className="mt-6">
        <HitlPanel
          caseId={caseId}
          history={reviewHistory}
          onHistoryChange={setReviewHistory}
          followUpQuestion={followUpQuestion}
          reviewItems={reviewItems}
          reviewItemHistory={reviewItemHistory}
          onReviewItemsChange={loadAll}
        />
      </section>
    </div>
  );
}
