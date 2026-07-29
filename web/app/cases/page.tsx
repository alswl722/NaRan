"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiGet, ApiError } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { CaseSummary } from "@/lib/types";

const IMPORTANCE_LABEL: Record<string, string> = {
  높음: "높음",
  보통: "보통",
  낮음: "낮음",
};

export default function QueuePage() {
  const [cases, setCases] = useState<CaseSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    apiGet<CaseSummary[]>("/cases")
      .then((data) => {
        if (alive) setCases(data);
      })
      .catch((err: unknown) => {
        if (alive) {
          setError(err instanceof ApiError ? err.message : "대기열을 불러오지 못했습니다");
        }
      });
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div className="w-full flex-1 px-8 py-8 lg:px-12">
      <header className="mb-6 step-enter">
        <h1 className="text-2xl font-bold text-ink-strong">사후관리 검토 대기열</h1>
        <p className="mt-2 text-[14px] text-muted">
          지속가능경영보고서의 환경 주장과 공개 환경 데이터를 비교 가능한 범위인지 먼저 검사한
          뒤, 비교 가능한 수치만 대조해 근거와 후속 확인 질문을 보여줍니다.
        </p>
      </header>

      {error && (
        <div className="mb-6 rounded-2xl border border-status-unexplained/30 bg-status-unexplained/5 px-5 py-4 text-[14px] text-status-unexplained">
          {error} — 백엔드 서버(기본 http://localhost:8000)가 실행 중인지 확인해 주세요.
        </div>
      )}

      {!cases && !error && (
        <div className="rounded-2xl border border-line bg-surface px-5 py-8 text-center text-[14px] text-faint">
          불러오는 중…
        </div>
      )}

      {cases && cases.length === 0 && (
        <div className="rounded-2xl border border-line bg-surface px-5 py-8 text-center text-[14px] text-faint">
          대기 중인 사례가 없습니다.
        </div>
      )}

      {cases && cases.length > 0 && (
        <div className="overflow-x-auto rounded-2xl border border-line bg-surface shadow-card step-enter">
          <table className="w-full min-w-[720px] text-left text-[13.5px]">
            <thead>
              <tr className="border-b border-line bg-bg text-[12px] text-faint">
                <th className="px-5 py-3 font-medium">기업</th>
                <th className="px-5 py-3 font-medium">보고서</th>
                <th className="px-5 py-3 font-medium">다음 점검일</th>
                <th className="px-5 py-3 font-medium" title="중요도는 AI 위험점수가 아닙니다">
                  중요도
                </th>
                <th className="px-5 py-3 font-medium">검토 상태</th>
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <CaseRow key={c.id} c={c} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function CaseRow({ c }: { c: CaseSummary }) {
  const needsReview = c.review_required === true;
  const notAnalyzed = c.review_required === null;

  return (
    <tr className="border-b border-line last:border-0 transition-colors hover:bg-bg">
      <td className="px-5 py-3.5">
        <Link href={`/cases/${c.id}`} className="flex items-center gap-2">
          <span className="font-semibold text-ink-strong hover:text-brand">
            {c.company_name ?? c.company_id}
          </span>
          {c.synthetic && (
            <span className="shrink-0 rounded-full bg-muted/15 px-2 py-0.5 text-[11px] font-medium text-muted">
              데모용 가상 여신 정보
            </span>
          )}
        </Link>
      </td>
      <td className="px-5 py-3.5 text-faint">
        {c.report_title ?? c.report_id} · {c.case_type}
      </td>
      <td className="px-5 py-3.5 tabular-nums text-ink">{formatDate(c.next_review_date)}</td>
      <td className="px-5 py-3.5 text-ink">{IMPORTANCE_LABEL[c.importance] ?? c.importance}</td>
      <td className="px-5 py-3.5">
        {notAnalyzed ? (
          <span className="rounded-full bg-faint/15 px-3 py-1 text-[12.5px] font-semibold text-faint">
            분석 전
          </span>
        ) : needsReview ? (
          <span className="rounded-full bg-brand-soft px-3 py-1 text-[12.5px] font-semibold text-ink-strong">
            검토 필요
          </span>
        ) : (
          <span className="rounded-full bg-status-match/10 px-3 py-1 text-[12.5px] font-semibold text-status-match">
            검토 불필요
          </span>
        )}
      </td>
    </tr>
  );
}
