"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { CaseSummary, ClaimDetail, ReviewRecord, RunSummary, TraceEvent } from "@/lib/types";
import { ClaimCard } from "@/components/ClaimCard";
import { TraceTimeline } from "@/components/TraceTimeline";
import { HitlPanel } from "@/components/HitlPanel";

/** run.logical_key("run-case-a-claim-a-scope1-fact-...")에서 이 run이 다룬
 * claim의 사람이 읽는 라벨(예: "Scope 1 온실가스 배출량")을 되짚는다. */
function runLabel(logicalKey: string, claims: ClaimDetail[]): string {
  const matched = claims.find((d) => logicalKey.includes(`-${d.claim.id}-`));
  if (!matched) return logicalKey;
  const { metric, scope } = matched.claim;
  return scope ? `${scope} ${metric}` : metric;
}

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
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    const summary = await apiGet<CaseSummary>(`/cases/${caseId}`);
    setCaseSummary(summary);

    const claims = await Promise.all(
      summary.claim_ids.map((cid) => apiGet<ClaimDetail>(`/claims/${cid}`)),
    );
    setClaimDetails(claims);

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
      await apiPost(`/cases/${caseId}/analyze`, undefined, 30_000);
      await loadAll();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "분석 실행에 실패했습니다");
    } finally {
      setAnalyzing(false);
    }
  }

  if (error && !caseSummary) {
    return (
      <div className="mx-auto w-full max-w-4xl px-5 py-10">
        <p className="text-[14px] text-status-unexplained">{error}</p>
        <Link href="/" className="mt-4 inline-block text-[13px] text-brand underline">
          대기열로 돌아가기
        </Link>
      </div>
    );
  }

  if (!caseSummary) {
    return (
      <div className="mx-auto w-full max-w-4xl px-5 py-10 text-[14px] text-faint">
        불러오는 중…
      </div>
    );
  }

  const analyzed = caseSummary.review_required !== null;
  const notComparableClaims = claimDetails.filter((d) =>
    d.comparisons.some((c) => c.verdict.status === "비교 불가"),
  );

  return (
    <div className="mx-auto w-full max-w-4xl flex-1 px-5 py-10">
      <Link href="/" className="text-[13px] text-faint hover:text-ink">
        ← 대기열로
      </Link>

      <header className="mt-3 mb-6 step-enter">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-bold text-ink-strong">
            {caseSummary.company_name ?? caseSummary.company_id}
          </h1>
          {caseSummary.synthetic && (
            <span className="rounded-full bg-muted/15 px-2.5 py-1 text-[11.5px] font-medium text-muted">
              데모용 가상 여신 정보 — 합성 사례
            </span>
          )}
        </div>
        <p className="mt-1 text-[14px] text-muted">
          {caseSummary.report_title} · {caseSummary.case_type}
        </p>

        <button
          type="button"
          onClick={runAnalysis}
          disabled={analyzing}
          className="mt-4 rounded-xl bg-brand px-5 py-2.5 text-[14px] font-semibold text-ink-strong shadow-float transition-transform hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {analyzing ? "분석 실행 중…" : analyzed ? "다시 분석 실행" : "분석 시작"}
        </button>
        {error && <p className="mt-2 text-[13px] text-status-unexplained">{error}</p>}
      </header>

      {/* 장면 2 — 비교 불가 사례는 계산 중단 사실을 가장 먼저 강조한다 */}
      {notComparableClaims.length > 0 && (
        <div className="mb-6 rounded-2xl border border-status-not-comparable/30 bg-status-not-comparable/5 p-5 step-enter">
          <h2 className="text-[14px] font-bold text-ink-strong">계산이 중단되었습니다</h2>
          <p className="mt-1 text-[13px] text-ink">
            보고서 값과 공개 데이터의 조직·지역 범위가 달라 차이를 계산하지 않았습니다. 동일한
            범위의 자료를 요청해 주세요.
          </p>
        </div>
      )}

      <section className="mb-8 flex flex-col gap-4">
        {claimDetails.map((detail) => (
          <ClaimCard key={detail.claim.id} detail={detail} />
        ))}
      </section>

      {runsWithTrace.length > 0 && (
        <section className="mb-8">
          <h2 className="mb-3 text-[15px] font-bold text-ink-strong">트레이스</h2>
          <div className="flex flex-col gap-4">
            {runsWithTrace.map(({ run, trace }) => (
              <div key={run.id} className="rounded-2xl border border-line bg-surface p-5 shadow-card">
                <div className="mb-3 flex items-center justify-between text-[12.5px]">
                  <span className="font-semibold text-ink-strong">
                    {runLabel(run.logical_key, claimDetails)}
                  </span>
                  <span className="text-faint">{formatDateTime(run.started_at)}</span>
                </div>
                <TraceTimeline events={trace} />
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="mb-8">
        <h2 className="mb-3 text-[15px] font-bold text-ink-strong">HITL</h2>
        <HitlPanel caseId={caseId} history={reviewHistory} onHistoryChange={setReviewHistory} />
      </section>
    </div>
  );
}
