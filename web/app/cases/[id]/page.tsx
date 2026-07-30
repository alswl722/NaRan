"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import type { CaseSummary, ClaimDetail, ReviewRecord, RunSummary, TraceEvent } from "@/lib/types";
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
          className="mt-4 rounded-xl bg-brand px-5 py-2.5 text-[14px] font-semibold text-ink-strong shadow-card disabled:cursor-not-allowed disabled:opacity-60"
        >
          {analyzing ? "분석 실행 중…" : analyzed ? "다시 분석 실행" : "분석 시작"}
        </button>
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
