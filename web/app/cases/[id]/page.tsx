"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";
import { ANALYZE_TIMEOUT_MS, apiGet, apiPost, ApiError } from "@/lib/api";
import type {
  AnalyzeExecution,
  AnalyzeResponse,
  CaseSummary,
  ClaimDetail,
  ReportPdfMeta,
  ReviewRecord,
  RunSummary,
  TraceEvent,
} from "@/lib/types";
import { ClaimCard } from "@/components/ClaimCard";
import { HitlPanel } from "@/components/HitlPanel";

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
  const [pdfAvailable, setPdfAvailable] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisMode, setAnalysisMode] = useState<"demo" | "live">("demo");
  const [allowCacheFallback, setAllowCacheFallback] = useState(true);
  const [lastExecution, setLastExecution] = useState<AnalyzeExecution | null>(null);
  const [error, setError] = useState<string | null>(null);

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
  }, [caseId]);

  useEffect(() => {
    let alive = true;
    async function run() {
      try {
        await loadAll();
      } catch (err) {
        if (alive) {
          setError(err instanceof ApiError ? err.message : "사례를 불러오지 못했습니다");
        }
      }
    }
    void run();
    return () => {
      alive = false;
    };
  }, [loadAll]);

  async function runAnalysis() {
    setAnalyzing(true);
    setError(null);
    try {
      const response = await apiPost<AnalyzeResponse>(
        `/cases/${caseId}/analyze`,
        {
          mode: analysisMode,
          allow_cache_fallback: analysisMode === "live" && allowCacheFallback,
        },
        ANALYZE_TIMEOUT_MS,
      );
      setLastExecution(response.execution);
      await loadAll();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "분석 실행에 실패했습니다");
    } finally {
      setAnalyzing(false);
    }
  }

  if (error && !caseSummary) {
    return (
      <div className="w-full px-8 py-8 lg:px-12">
        <p className="text-[14px] text-status-unexplained">{error}</p>
        <Link href="/cases" className="mt-4 inline-block text-[13px] text-brand underline">
          대기열로 돌아가기
        </Link>
      </div>
    );
  }

  if (!caseSummary) {
    return (
      <div className="w-full px-8 py-8 text-[14px] text-faint lg:px-12">불러오는 중…</div>
    );
  }

  const analyzed = caseSummary.review_required !== null;
  const notComparableClaims = claimDetails.filter((d) =>
    d.comparisons.some((c) => c.verdict.status === "비교 불가"),
  );
  const followUpQuestion =
    claimDetails
      .flatMap((d) => d.comparisons.map((c) => c.verdict.follow_up_question))
      .find((q) => q !== null) ?? null;

  return (
    <div className="w-full flex-1 px-8 py-8 lg:px-12">
      <Link href="/cases" className="text-[13px] text-faint hover:text-ink">
        ← 대기열로
      </Link>

      <header className="mt-3 mb-6">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-bold text-ink-strong">
            {caseSummary.company_name ?? caseSummary.company_id}
          </h1>
          {caseSummary.monitoring_data_synthetic && (
            <span className="rounded-full bg-muted/15 px-2.5 py-1 text-[11.5px] font-medium text-muted">
              {caseSummary.evidence_data_synthetic
                ? "완전 합성 사례"
                : "실제 공개자료 · 여신정보 데모"}
            </span>
          )}
        </div>
        <p className="mt-1 text-[14px] text-muted">
          {caseSummary.report_title} · {caseSummary.case_type}
        </p>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <div className="flex rounded-xl border border-line bg-white p-1">
            <button
              type="button"
              onClick={() => setAnalysisMode("demo")}
              disabled={analyzing}
              className={`rounded-lg px-3 py-1.5 text-[12.5px] font-semibold ${
                analysisMode === "demo" ? "bg-ink-strong text-white" : "text-muted"
              }`}
            >
              저장값 데모
            </button>
            <button
              type="button"
              onClick={() => setAnalysisMode("live")}
              disabled={analyzing}
              className={`rounded-lg px-3 py-1.5 text-[12.5px] font-semibold ${
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
            className="rounded-xl bg-brand px-5 py-2.5 text-[14px] font-semibold text-ink-strong shadow-card disabled:cursor-not-allowed disabled:opacity-60"
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
        {analysisMode === "live" && (
          <label className="mt-2 flex items-center gap-2 text-[12.5px] text-muted">
            <input
              type="checkbox"
              checked={allowCacheFallback}
              onChange={(event) => setAllowCacheFallback(event.target.checked)}
              disabled={analyzing}
              className="accent-brand"
            />
            Gemini 실패 시 검증된 저장값 사용
          </label>
        )}
        {lastExecution && (
          <div
            className={`mt-3 rounded-xl border px-4 py-3 text-[12.5px] ${
              lastExecution.execution_mode === "live"
                ? "border-emerald-300 bg-emerald-50 text-emerald-900"
                : lastExecution.execution_mode === "fallback"
                  ? "border-amber-300 bg-amber-50 text-amber-900"
                  : "border-line bg-white text-muted"
            }`}
          >
            <span className="font-bold">
              {lastExecution.execution_mode === "live"
                ? "LIVE · Gemini 실시간 추출"
                : lastExecution.execution_mode === "fallback"
                  ? "FALLBACK · 저장값 사용"
                  : "DEMO · 검증 저장값"}
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
              <p className="mt-1">
                공개 데이터가 없어 대조를 건너뛴 주장{" "}
                {lastExecution.skipped_claims.length}건
              </p>
            )}
          </div>
        )}
        {error && <p className="mt-2 text-[13px] text-status-unexplained">{error}</p>}
      </header>

      {/* 장면 2 — 비교 불가 사례는 계산 중단 사실을 가장 먼저 강조한다 */}
      {notComparableClaims.length > 0 && (
        <div className="mb-6 flex items-start gap-2.5 rounded-2xl bg-brand-soft p-5">
          <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand" />
          <div>
            <h2 className="text-[14px] font-bold text-ink-strong">계산이 중단되었습니다</h2>
            <p className="mt-1 text-[13px] text-ink">
              보고서 값과 공개 데이터의 조직·지역 범위가 달라 차이를 계산하지 않았습니다. 동일한
              범위의 자료를 요청해 주세요.
            </p>
          </div>
        </div>
      )}

      {/* 주장 카드(장면 3·4) + 그 주장을 다룬 실행의 트레이스(장면 2) —
          나란히 대조 뷰가 넓은 폭을 쓰므로 전체 폭 1단으로 배치한다 */}
      <section className="flex flex-col gap-4">
        {claimDetails.map((detail) => (
          <ClaimCard
            key={detail.claim.id}
            detail={detail}
            runs={runsWithTrace.filter(({ run }) =>
              run.logical_key.includes(`-${detail.claim.id}-`),
            )}
            pdfAvailable={pdfAvailable}
          />
        ))}
      </section>

      {/* HITL — claim 카드들 아래, 전체 폭으로 배치해 사이드바 좁은 폭 제약을 없앤다 */}
      <section className="mt-6">
        <h2 className="mb-3 text-[15px] font-bold text-ink-strong">HITL</h2>
        <HitlPanel
          caseId={caseId}
          history={reviewHistory}
          onHistoryChange={setReviewHistory}
          followUpQuestion={followUpQuestion}
        />
      </section>
    </div>
  );
}
