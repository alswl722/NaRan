"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiGet, ApiError } from "@/lib/api";
import { formatDecimal, formatValueWithUnit } from "@/lib/format";
import { StatusBadge } from "@/components/StatusBadge";
import type { AnalysisStatus, CaseSummary, ClaimDetail } from "@/lib/types";

type CaseWithClaims = { case: CaseSummary; claims: ClaimDetail[] };

type Finding = {
  caseId: string;
  company: string;
  metricLabel: string;
  status: AnalysisStatus;
  explanation: string;
  absoluteDifference: string | null;
  relativeDifferencePct: string | null;
  unit: string | null;
};

// 실제로 눈에 띄어야 할 상태부터 — 나란의 핵심 장면(계산 중단)이 최우선
const FINDING_PRIORITY: AnalysisStatus[] = [
  "비교 불가",
  "설명되지 않은 차이",
  "설명 가능성 있음",
  "일치",
  "설명된 차이",
  "정보 부족",
];

export default function DashboardPage() {
  const [data, setData] = useState<CaseWithClaims[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const cases = await apiGet<CaseSummary[]>("/cases");
      const withClaims = await Promise.all(
        cases.map(async (c) => ({
          case: c,
          claims: await Promise.all(
            c.claim_ids.map((cid) => apiGet<ClaimDetail>(`/claims/${cid}`)),
          ),
        })),
      );
      setData(withClaims);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "현황을 불러오지 못했습니다");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    async function run() {
      await load();
    }
    void run();
  }, [load]);

  if (error && !data) {
    return (
      <div className="w-full flex-1 px-8 py-8 lg:px-12">
        <p className="text-[14px] text-status-unexplained">{error}</p>
        <p className="mt-2 text-[13px] text-faint">
          백엔드 서버(기본 http://localhost:8000)가 실행 중인지 확인해 주세요.
        </p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="w-full flex-1 px-8 py-8 text-[14px] text-faint lg:px-12">불러오는 중…</div>
    );
  }

  const totalCases = data.length;
  const analyzedCount = data.filter((d) => d.case.review_required !== null).length;
  const reviewRequiredCount = data.filter((d) => d.case.review_required === true).length;

  const verdicts = data.flatMap((d) =>
    d.claims.flatMap((cd) =>
      cd.comparisons.map((cmp) => ({
        caseId: d.case.id,
        company: d.case.company_name ?? d.case.company_id,
        metric: cd.claim.metric,
        scope: cd.claim.scope,
        unit: cd.claim.unit,
        verdict: cmp.verdict,
      })),
    ),
  );

  const notComparableCount = verdicts.filter((v) => v.verdict.status === "비교 불가").length;

  const findings: Finding[] = [];
  for (const status of FINDING_PRIORITY) {
    const hit = verdicts.find((v) => v.verdict.status === status);
    if (hit) {
      findings.push({
        caseId: hit.caseId,
        company: hit.company,
        metricLabel: hit.scope ? `${hit.scope} ${hit.metric}` : hit.metric,
        status: hit.verdict.status,
        explanation: hit.verdict.explanation,
        absoluteDifference: hit.verdict.absolute_difference,
        relativeDifferencePct: hit.verdict.relative_difference_pct,
        unit: hit.unit,
      });
    }
    if (findings.length >= 3) break;
  }

  return (
    <div className="w-full flex-1 px-8 py-8 lg:px-12">
      <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-ink-strong">여신 사후관리 현황</h1>
          <p className="mt-1.5 text-[13px] text-faint">
            비교 가능한 값만 대조한 실시간 집계입니다
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={load}
            disabled={loading}
            className="rounded-xl bg-surface px-4 py-2 text-[13px] font-semibold text-muted shadow-card hover:text-ink-strong disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "새로고침 중…" : "새로고침"}
          </button>
          <Link
            href="/cases"
            className="rounded-xl bg-brand px-4 py-2 text-[13px] font-bold text-ink-strong shadow-card"
          >
            대기열 전체 보기 →
          </Link>
        </div>
      </header>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatTile label="총 관리 건수" value={`${totalCases}`} unit="건" />
        <StatTile label="분석 완료" value={`${analyzedCount}`} unit={`/ ${totalCases}건`} />
        <StatTile
          label="검토 필요"
          value={`${reviewRequiredCount}`}
          unit="건"
          accent={reviewRequiredCount > 0}
        />
        <StatTile
          label="계산 중단 (비교 불가)"
          value={`${notComparableCount}`}
          unit="건"
          accent={notComparableCount > 0}
        />
      </div>

      {findings.length > 0 && (
        <section className="mt-6">
          <h2 className="text-[14.5px] font-bold text-ink-strong">최근 판단 근거</h2>
          <div className="mt-3 grid grid-cols-1 gap-4 md:grid-cols-3">
            {findings.map((f) => (
              <Link
                key={`${f.caseId}-${f.status}`}
                href={`/cases/${f.caseId}`}
                className="flex flex-col gap-1.5 rounded-2xl bg-surface p-4 shadow-card"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[12.5px] font-bold text-ink-strong">{f.company}</span>
                  <StatusBadge status={f.status} />
                </div>
                <div className="text-[11.5px] text-faint">{f.metricLabel}</div>
                <p className="text-[12.5px] leading-relaxed text-ink">{f.explanation}</p>
                {f.absoluteDifference !== null && (
                  <p className="mt-1 text-[12px] tabular-nums text-ink-strong">
                    수치 차이 {formatValueWithUnit(f.absoluteDifference, f.unit)}
                    {f.relativeDifferencePct !== null &&
                      ` · 상대 차이율 ${formatDecimal(f.relativeDifferencePct)}%`}
                  </p>
                )}
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function StatTile({
  label,
  value,
  unit,
  accent,
}: {
  label: string;
  value: string;
  unit?: string;
  accent?: boolean;
}) {
  return (
    <div className="rounded-2xl bg-surface p-4 shadow-card">
      <div className="flex items-center gap-1.5">
        {accent && <span className="h-1.5 w-4 shrink-0 rounded-full bg-brand" />}
        <span className="text-[12.5px] font-medium text-muted">{label}</span>
      </div>
      <div className="mt-1.5 flex items-baseline gap-1">
        <span className="text-[26px] font-extrabold tabular-nums text-ink-strong">{value}</span>
        {unit && <span className="text-[12px] font-medium text-faint">{unit}</span>}
      </div>
    </div>
  );
}
