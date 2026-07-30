"use client";

import { useEffect, useRef, useState } from "react";

/**
 * 랜딩 히어로의 시그니처 요소 — 실제 오케스트레이터가 남기는
 * [계획]/[관찰]/[행동] 트레이스 포맷 그대로, B 사례(claude.md 8절)의
 * "계산 중단" 흐름을 재생한다. 나란의 핵심 차별점은 숫자 차이를 찾는
 * 장면이 아니라 범위가 다른 숫자의 계산을 멈추는 장면이라, 랜딩에서도
 * 그 장면을 가장 먼저 보여준다.
 */

type StepType = "계획" | "관찰" | "행동";

const STEP_ICON: Record<StepType, string> = {
  계획: "◇",
  관찰: "◎",
  행동: "▶",
};

const STEP_DOT: Record<StepType, string> = {
  계획: "bg-faint",
  관찰: "bg-status-explained",
  행동: "bg-brand",
};

type LogLine = { type: StepType; tool: string; message: string };

const SCRIPT: LogLine[] = [
  { type: "계획", tool: "", message: "주장 근거 확인 → 공개 데이터 확인 → 비교 가능성 검사 → 조건부 수치 대조" },
  { type: "관찰", tool: "claim.verified_input", message: "실적주장 · 온실가스 배출량 · 보고서 p.68 확인" },
  {
    type: "행동",
    tool: "public_data.snapshot",
    message: "환경정보공개시스템 수원사업장 데이터 조회 완료",
  },
  { type: "관찰", tool: "comparability.check", message: "조직경계 불일치 · 지역경계 불일치 확인 — 연결 전사 vs 개별 사업장" },
  { type: "행동", tool: "compare.stop", message: "조직 및 지역 범위가 달라 계산을 중단함" },
  { type: "행동", tool: "review.route", message: "동일 범위 자료 요청과 함께 담당자 검토 대기열로 전달" },
];

const BASE_SECONDS = 9 * 3600 + 41 * 60; // 고정 합성 시각(하이드레이션 안전)

function fmtClock(stepIndex: number, cycle: number) {
  const total = BASE_SECONDS + cycle * 34 + stepIndex * 4;
  const h = Math.floor(total / 3600) % 24;
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return [h, m, s].map((n) => String(n).padStart(2, "0")).join(":");
}

const TICK_MS = 2200;

function prefersReducedMotion(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function LiveTraceFeed() {
  const [count, setCount] = useState(() => (prefersReducedMotion() ? SCRIPT.length : 2));
  const [cycle, setCycle] = useState(0);
  const [paused, setPaused] = useState(false);
  const listRef = useRef<HTMLOListElement>(null);

  useEffect(() => {
    if (prefersReducedMotion() || paused) return;
    const id = setInterval(() => {
      setCount((c) => {
        if (c >= SCRIPT.length) {
          setCycle((cy) => cy + 1);
          return 2;
        }
        return c + 1;
      });
    }, TICK_MS);
    return () => clearInterval(id);
  }, [paused]);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [count]);

  const rows = SCRIPT.slice(0, count);

  return (
    <div
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      className="w-full max-w-md overflow-hidden rounded-3xl border border-line bg-surface shadow-card"
    >
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-brand" />
          </span>
          <span className="text-[13.5px] font-bold tracking-wide text-ink-strong">
            실제 분석 과정
          </span>
          <span className="rounded-full bg-brand-soft px-2 py-0.5 text-[12.5px] font-semibold text-ink-strong">
            사례 B · 삼성전자
          </span>
        </div>
        <button
          type="button"
          onClick={() => {
            setCount(2);
            setCycle((c) => c + 1);
          }}
          aria-label="처음부터 다시 재생"
          className="rounded-full p-1.5 text-faint transition-colors hover:bg-bg hover:text-muted"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
            <path d="M3 12a9 9 0 1 0 3-6.7" />
            <path d="M3 4v5h5" />
          </svg>
        </button>
      </div>

      <ol ref={listRef} className="h-[300px] space-y-0 overflow-y-auto px-4 py-3.5">
        {rows.map((row, i) => {
          const last = i === rows.length - 1;
          const isStop = row.tool === "compare.stop";
          return (
            <li key={`${cycle}-${i}`} className="step-enter relative flex gap-3 pb-4 last:pb-0">
              {!last && <span className="absolute left-[7px] top-4 h-full w-px bg-line" />}
              <span
                className={`relative z-10 mt-0.5 grid h-[15px] w-[15px] shrink-0 place-items-center rounded-full text-[11px] text-white ${
                  isStop ? "bg-status-not-comparable" : STEP_DOT[row.type]
                }`}
              >
                {STEP_ICON[row.type]}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-[12.5px] font-bold text-ink-strong">{row.type}</span>
                  {row.tool && (
                    <span className="rounded bg-bg px-1.5 py-0.5 font-mono text-[12.5px] text-muted">
                      {row.tool}
                    </span>
                  )}
                  <span className="ml-auto font-mono text-[12.5px] text-faint">
                    {fmtClock(i, cycle)}
                  </span>
                </div>
                <p className={`mt-1 text-[14px] leading-snug ${isStop ? "font-semibold text-status-not-comparable" : "text-ink"}`}>
                  {row.message}
                </p>
              </div>
            </li>
          );
        })}
        {count < SCRIPT.length && (
          <li className="flex items-center gap-2 pl-6 text-[13px] text-faint">
            <span className="flex gap-1">
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-faint [animation-delay:-0.3s]" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-faint [animation-delay:-0.15s]" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-faint" />
            </span>
            판단 중…
          </li>
        )}
      </ol>
    </div>
  );
}
