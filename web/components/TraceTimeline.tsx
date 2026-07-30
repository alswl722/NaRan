import type { TraceEvent } from "@/lib/types";

/** 트레이스는 실행마다 쌓인다 — 고정 높이 스크롤 영역 안에 한 줄 요약으로 담고,
 * 도구명·근거처럼 감사에만 필요한 세부 정보는 펼치기 전까지 숨긴다. */
export function TraceTimeline({ events }: { events: TraceEvent[] }) {
  if (events.length === 0) {
    return <p className="text-[13px] text-faint">기록된 분석 과정이 없습니다.</p>;
  }

  return (
    <div className="max-h-80 overflow-y-auto pr-1">
      <ol className="flex flex-col">
        {events.map((event, i) => {
          const isStop = event.stage === "계산 중단" || event.stage === "목표 계산 중단";
          const last = i === events.length - 1;
          const hasDetail = event.tool_name || event.evidence.length > 0;
          return (
            <li key={i} className="relative flex gap-3 pb-3 last:pb-0">
              {!last && <span className="absolute left-[5px] top-4 h-full w-px bg-line" />}
              <span
                className={`relative z-10 mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${
                  isStop ? "bg-brand" : "bg-faint"
                }`}
              />
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline gap-1.5">
                  <span className="shrink-0 text-[11px] font-medium text-faint">
                    {event.step_type}
                  </span>
                  <span className="truncate text-[13px] font-semibold text-ink-strong">
                    {event.stage}
                  </span>
                </div>
                <p
                  className="mt-0.5 truncate text-[12.5px] text-ink"
                  title={event.input_summary}
                >
                  {event.input_summary}
                </p>
                {hasDetail && (
                  <details className="mt-0.5">
                    <summary className="cursor-pointer text-[11px] text-faint select-none">
                      세부 정보
                    </summary>
                    <div className="mt-1 flex flex-col gap-0.5">
                      {event.tool_name && (
                        <span className="font-mono text-[11px] text-muted">
                          {event.tool_name}
                        </span>
                      )}
                      {event.evidence.map((e, j) => (
                        <span key={j} className="text-[11.5px] text-faint">
                          · {e}
                        </span>
                      ))}
                    </div>
                  </details>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
