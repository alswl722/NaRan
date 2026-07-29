"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiGet, ApiError } from "@/lib/api";
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
    <div className="mx-auto w-full max-w-4xl flex-1 px-5 py-10">
      <header className="mb-8 step-enter">
        <h1 className="text-2xl font-bold text-ink-strong">사후관리 검토 대기열</h1>
        <p className="mt-2 text-[15px] text-muted">
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

      <ul className="flex flex-col gap-3">
        {cases?.map((c, i) => (
          <li key={c.id} className="step-enter" style={{ animationDelay: `${i * 60}ms` }}>
            <CaseRow c={c} />
          </li>
        ))}
      </ul>
    </div>
  );
}

function CaseRow({ c }: { c: CaseSummary }) {
  const needsReview = c.review_required === true;
  const notAnalyzed = c.review_required === null;

  return (
    <Link
      href={`/cases/${c.id}`}
      className="flex items-center justify-between gap-4 rounded-2xl border border-line bg-surface px-5 py-4 shadow-card transition-transform hover:-translate-y-0.5"
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-[15px] font-semibold text-ink-strong">
            {c.company_name ?? c.company_id}
          </span>
          {c.synthetic && (
            <span className="shrink-0 rounded-full bg-muted/15 px-2 py-0.5 text-[11px] font-medium text-muted">
              데모용 가상 여신 정보
            </span>
          )}
        </div>
        <div className="mt-1 truncate text-[13px] text-faint">
          {c.report_title ?? c.report_id} · {c.case_type}
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-3">
        <div className="text-right">
          <div className="text-[12px] text-faint">다음 점검일</div>
          <div className="text-[13px] font-medium text-ink">{c.next_review_date}</div>
        </div>
        <div className="text-right" title="중요도는 AI 위험점수가 아닙니다">
          <div className="text-[12px] text-faint">중요도</div>
          <div className="text-[13px] font-medium text-ink">
            {IMPORTANCE_LABEL[c.importance] ?? c.importance}
          </div>
        </div>
        {notAnalyzed ? (
          <span className="rounded-full bg-faint/15 px-3 py-1 text-[13px] font-semibold text-faint">
            분석 전
          </span>
        ) : needsReview ? (
          <span className="rounded-full bg-brand-soft px-3 py-1 text-[13px] font-semibold text-ink-strong">
            검토 필요
          </span>
        ) : (
          <span className="rounded-full bg-status-match/10 px-3 py-1 text-[13px] font-semibold text-status-match">
            검토 불필요
          </span>
        )}
      </div>
    </Link>
  );
}
