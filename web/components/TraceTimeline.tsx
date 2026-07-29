import type { TraceEvent, TraceStepType } from "@/lib/types";

/** 색이 아니라 아이콘 모양 + 텍스트 라벨로 계획/관찰/행동을 구분한다. */
const STEP_ICON: Record<TraceStepType, string> = {
  계획: "◇",
  관찰: "◎",
  행동: "▶",
};

export function TraceTimeline({ events }: { events: TraceEvent[] }) {
  if (events.length === 0) {
    return <p className="text-[13px] text-faint">트레이스가 없습니다.</p>;
  }

  return (
    <ol className="flex flex-col gap-2">
      {events.map((event, i) => {
        const isStop = event.stage === "계산 중단" || event.stage === "목표 계산 중단";
        return (
          <li
            key={i}
            className="trace-enter rounded-xl border border-line bg-surface px-4 py-3"
            style={{ animationDelay: `${i * 70}ms` }}
          >
            <div className="flex items-start gap-2.5">
              <span
                className="mt-0.5 shrink-0 text-[13px]"
                style={{ color: isStop ? "var(--color-status-not-comparable)" : "var(--color-ink)" }}
              >
                {STEP_ICON[event.step_type]}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-baseline gap-x-2">
                  <span className="text-[11px] font-medium text-faint">{event.step_type}</span>
                  <span
                    className={`text-[13.5px] font-semibold ${
                      isStop ? "text-status-not-comparable" : "text-ink-strong"
                    }`}
                  >
                    {event.stage}
                  </span>
                  {event.tool_name && (
                    <span className="font-mono text-[11px] text-faint">{event.tool_name}</span>
                  )}
                </div>
                <p className="mt-0.5 text-[13.5px] leading-relaxed text-ink">
                  {event.input_summary}
                </p>
                {event.evidence.length > 0 && (
                  <ul className="mt-1.5 flex flex-col gap-0.5">
                    {event.evidence.map((e, j) => (
                      <li key={j} className="text-[12px] text-faint">
                        · {e}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
