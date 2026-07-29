"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiGet, ApiError } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { LiveTraceFeed } from "@/components/LiveTraceFeed";
import type { CaseSummary } from "@/lib/types";

const IMPORTANCE_LABEL: Record<string, string> = {
  높음: "높음",
  보통: "보통",
  낮음: "낮음",
};

const STEPS = [
  {
    t: "사후관리 검토 대기열",
    preview: "보고서가 연결된 관리 건을 검토 필요 순으로 모아둡니다",
  },
  {
    t: "비교 가능성 먼저 검사",
    preview: "조직·지역·Scope·산정 방식이 같은 값인지부터 확인해요",
  },
  {
    t: "다른 범위는 계산 중단",
    preview: "숫자가 달라 보여도 범위가 다르면 차이를 계산하지 않아요",
  },
  {
    t: "근거와 후속 질문",
    preview: "원문·페이지·출처를 남기고, 담당자 확인 질문까지 준비해요",
  },
];

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
    <div className="flex flex-1 flex-col items-center px-5 pb-20">
      {/* 히어로 */}
      <div className="grid w-full max-w-5xl items-center gap-12 pt-14 lg:grid-cols-[1fr_1fr] lg:gap-8 lg:pt-20">
        <div className="text-center lg:text-left">
          <span
            className="hero-enter inline-flex items-center gap-1.5 rounded-full bg-brand-soft px-3 py-1.5 text-[11.5px] font-bold tracking-wide text-ink-strong"
            style={{ animationDelay: "0ms" }}
          >
            <span className="h-1.5 w-1.5 rounded-full bg-brand" />
            AI 사후관리 보조 도구
          </span>

          <h1
            className="hero-enter mt-5 text-[34px] font-extrabold leading-[1.22] tracking-[-0.02em] text-ink-strong lg:text-[42px]"
            style={{ animationDelay: "90ms" }}
          >
            비교할 수 없는 숫자는
            <br />
            <span className="text-brand">계산을 멈춥니다</span>
          </h1>

          <p
            className="hero-enter mt-5 text-[15px] leading-relaxed text-muted lg:max-w-md"
            style={{ animationDelay: "140ms" }}
          >
            지속가능경영보고서의 환경 주장과 공개 환경 데이터가 비교 가능한
            범위인지 먼저 검사하고, 비교 가능한 수치만 대조해 근거와 후속
            확인 질문을 보여줍니다.
          </p>

          <div
            className="hero-enter mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center lg:justify-start"
            style={{ animationDelay: "180ms" }}
          >
            <a
              href="#queue"
              className="rounded-2xl bg-brand px-8 py-4 text-[15.5px] font-bold text-ink-strong shadow-float transition-transform hover:-translate-y-0.5"
            >
              대기열 확인하기 →
            </a>
          </div>
        </div>

        <div
          className="hero-enter flex justify-center lg:justify-end"
          style={{ animationDelay: "240ms" }}
        >
          <LiveTraceFeed />
        </div>
      </div>

      <ol className="mt-20 grid w-full max-w-5xl gap-3 text-left sm:grid-cols-2 lg:grid-cols-4">
        {STEPS.map((s, i) => (
          <li
            key={s.t}
            className="hero-enter group relative overflow-hidden rounded-2xl bg-surface p-4 shadow-card transition-all duration-300 hover:-translate-y-1 hover:shadow-float"
            style={{ animationDelay: `${320 + i * 70}ms` }}
          >
            <div className="flex items-center gap-3">
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-brand-soft text-[13px] font-extrabold text-ink-strong transition-colors duration-300 group-hover:bg-brand">
                {i + 1}
              </span>
              <div className="text-[15.5px] font-bold text-ink-strong">{s.t}</div>
            </div>

            <div className="grid grid-rows-[0fr] transition-[grid-template-rows] duration-300 ease-out group-hover:grid-rows-[1fr]">
              <div className="overflow-hidden">
                <div className="mt-1 break-keep text-[13.5px] leading-relaxed text-muted">
                  {s.preview}
                </div>
              </div>
            </div>
          </li>
        ))}
      </ol>

      {/* 대기열 */}
      <div id="queue" className="mx-auto w-full max-w-4xl scroll-mt-20 pt-20">
        <header className="mb-8 step-enter">
          <h2 className="text-2xl font-bold text-ink-strong">사후관리 검토 대기열</h2>
          <p className="mt-2 text-[15px] text-muted">
            검토가 필요한 관리 건부터 순서대로 보여줍니다.
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
          <div className="text-[13px] font-medium text-ink">{formatDate(c.next_review_date)}</div>
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
