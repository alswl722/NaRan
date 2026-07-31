"use client";

import { useEffect, useRef } from "react";
import type { AnalysisProgress } from "@/lib/types";

const STEP_ICON = {
  계획: "◇",
  관찰: "◎",
  행동: "▶",
} as const;

const STEP_COLOR = {
  계획: "bg-faint",
  관찰: "bg-status-explained",
  행동: "bg-brand",
} as const;

function timeLabel(value: string) {
  return new Intl.DateTimeFormat("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

export function AnalysisProgressPanel({
  progress,
}: {
  progress: AnalysisProgress;
}) {
  const listRef = useRef<HTMLOListElement>(null);
  const running = progress.status === "running";

  useEffect(() => {
    listRef.current?.scrollTo({
      top: listRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [progress.events.length]);

  return (
    <aside className="overflow-hidden rounded-sm border border-line bg-white shadow-card lg:sticky lg:top-6">
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            {running && (
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand opacity-75" />
            )}
            <span
              className={`relative inline-flex h-2 w-2 rounded-full ${
                progress.status === "failed"
                  ? "bg-status-unexplained"
                  : progress.status === "completed"
                    ? "bg-emerald-500"
                    : "bg-brand"
              }`}
            />
          </span>
          <h2 className="text-[14px] font-bold text-ink-strong">
            AI Agent 분석 과정
          </h2>
        </div>
        <span className="text-[12px] font-semibold text-muted">
          {progress.status === "completed"
            ? "완료"
            : progress.status === "failed"
              ? "중단"
              : `${progress.current} / ${progress.total}`}
        </span>
      </div>

      <ol
        ref={listRef}
        aria-live="polite"
        className="max-h-[310px] min-h-[210px] overflow-y-auto px-4 py-3"
      >
        {progress.events.map((event, index) => {
          const last = index === progress.events.length - 1;
          return (
            <li key={event.id} className="step-enter relative flex gap-3 pb-4 last:pb-0">
              {!last && (
                <span className="absolute left-[7px] top-4 h-full w-px bg-line" />
              )}
              <span
                className={`relative z-10 mt-0.5 grid h-[15px] w-[15px] shrink-0 place-items-center rounded-full text-[9px] text-white ${STEP_COLOR[event.step_type]}`}
              >
                {STEP_ICON[event.step_type]}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-[11px] font-bold text-ink-strong">
                    {event.step_type}
                  </span>
                  <span className="rounded bg-bg px-1.5 py-0.5 text-[10.5px] font-medium text-muted">
                    {event.stage}
                  </span>
                  <span className="ml-auto font-mono text-[10px] text-faint">
                    {timeLabel(event.created_at)}
                  </span>
                </div>
                <p className="mt-1 text-[12.5px] leading-snug text-ink">
                  {event.message}
                </p>
              </div>
            </li>
          );
        })}
        {running && (
          <li className="flex items-center gap-2 pl-6 pt-2 text-[11.5px] text-faint">
            <span className="flex gap-1">
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-brand [animation-delay:-0.3s]" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-brand [animation-delay:-0.15s]" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-brand" />
            </span>
            다음 단계 진행 중…
          </li>
        )}
      </ol>
    </aside>
  );
}
