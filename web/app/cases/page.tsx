"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { apiGet, ApiError } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { CaseSummary } from "@/lib/types";

const IMPORTANCE_LABEL: Record<string, string> = {
  높음: "높음",
  보통: "보통",
  낮음: "낮음",
};

type StatusFilter = "전체" | "검토 필요" | "검토 불필요" | "분석 전";
const STATUS_TABS: StatusFilter[] = ["전체", "검토 필요", "검토 불필요", "분석 전"];

function matchesStatus(c: CaseSummary, filter: StatusFilter): boolean {
  if (filter === "전체") return true;
  if (filter === "분석 전") return c.review_required === null;
  if (filter === "검토 필요") return c.review_required === true;
  return c.review_required === false;
}

export default function QueuePage() {
  const [cases, setCases] = useState<CaseSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("전체");
  const [importanceFilter, setImportanceFilter] = useState("전체");
  const [search, setSearch] = useState("");

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

  const filtered = useMemo(() => {
    if (!cases) return null;
    const q = search.trim().toLowerCase();
    return cases.filter((c) => {
      if (!matchesStatus(c, statusFilter)) return false;
      if (importanceFilter !== "전체" && c.importance !== importanceFilter) return false;
      if (q) {
        const haystack = `${c.company_name ?? ""} ${c.company_id} ${c.report_title ?? ""}`.toLowerCase();
        if (!haystack.includes(q)) return false;
      }
      return true;
    });
  }, [cases, statusFilter, importanceFilter, search]);

  const filtersActive = statusFilter !== "전체" || importanceFilter !== "전체" || search.trim() !== "";

  return (
    <div className="w-full flex-1 px-8 py-8 lg:px-12">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-ink-strong">여신 사후관리 검토 대기열</h1>
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

      {cases && cases.length > 0 && (
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <div className="flex flex-wrap items-center gap-1.5">
            {STATUS_TABS.map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => setStatusFilter(tab)}
                className={`rounded-full px-3.5 py-2 text-[13px] font-semibold shadow-card ${
                  statusFilter === tab
                    ? "bg-brand text-ink-strong"
                    : "bg-surface text-muted hover:text-ink-strong"
                }`}
              >
                {tab}
              </button>
            ))}
          </div>

          <select
            value={importanceFilter}
            onChange={(e) => setImportanceFilter(e.target.value)}
            className="rounded-full bg-surface px-3.5 py-2 text-[13px] font-semibold text-muted shadow-card outline-none focus:ring-2 focus:ring-brand"
          >
            <option value="전체">전체 중요도</option>
            <option value="높음">높음</option>
            <option value="보통">보통</option>
            <option value="낮음">낮음</option>
          </select>

          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="기업명·보고서 검색"
            className="rounded-full bg-surface px-3.5 py-2 text-[13px] shadow-card outline-none focus:ring-2 focus:ring-brand"
          />

          {filtersActive && (
            <button
              type="button"
              onClick={() => {
                setStatusFilter("전체");
                setImportanceFilter("전체");
                setSearch("");
              }}
              className="rounded-full bg-surface px-3.5 py-2 text-[13px] font-semibold text-faint shadow-card hover:text-ink-strong"
            >
              초기화
            </button>
          )}

          <span className="ml-auto text-[12.5px] text-faint">
            {filtered?.length ?? 0}건 표시 · 전체 {cases.length}건
          </span>
        </div>
      )}

      {!cases && !error && (
        <div className="rounded-2xl bg-surface px-5 py-8 text-center text-[14px] text-faint shadow-card">
          불러오는 중…
        </div>
      )}

      {cases && cases.length === 0 && (
        <div className="rounded-2xl bg-surface px-5 py-8 text-center text-[14px] text-faint shadow-card">
          대기 중인 사례가 없습니다.
        </div>
      )}

      {filtered && cases && cases.length > 0 && filtered.length === 0 && (
        <div className="rounded-2xl bg-surface px-5 py-8 text-center text-[14px] text-faint shadow-card">
          조건에 맞는 사례가 없습니다.
        </div>
      )}

      {filtered && filtered.length > 0 && (
        <div className="overflow-x-auto rounded-2xl bg-surface shadow-card">
          <table className="w-full min-w-[720px] text-left text-[13.5px]">
            <thead>
              <tr className="border-b border-line text-[12px] text-faint">
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
              {filtered.map((c) => (
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
    <tr className="border-b border-line last:border-0 hover:bg-bg">
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
          <span className="rounded-full bg-bg px-3 py-1 text-[12.5px] font-semibold text-muted">
            검토 불필요
          </span>
        )}
      </td>
    </tr>
  );
}
