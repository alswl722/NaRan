import { STATUS_COLOR_VAR, STATUS_LABEL } from "@/lib/status";
import type { AnalysisStatus } from "@/lib/types";

// 여섯 상태를 한눈에 구분할 수 있도록 상태색을 쓴다 — 배경은 옅은 틴트,
// 글씨·점은 진한 상태색. "비교 불가"는 위험이 아니라 중립(회색) 상태다.
export function StatusBadge({ status }: { status: AnalysisStatus }) {
  const color = STATUS_COLOR_VAR[status];
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[14.5px] font-semibold"
      style={{ backgroundColor: `color-mix(in srgb, ${color} 14%, white)`, color }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color }} />
      {STATUS_LABEL[status]}
    </span>
  );
}
