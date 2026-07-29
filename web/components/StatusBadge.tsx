import { STATUS_COLOR_VAR, STATUS_LABEL } from "@/lib/status";
import type { AnalysisStatus } from "@/lib/types";

export function StatusBadge({ status }: { status: AnalysisStatus }) {
  const color = STATUS_COLOR_VAR[status];
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[13px] font-semibold"
      style={{ backgroundColor: `${color}1a`, color }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color }} />
      {STATUS_LABEL[status]}
    </span>
  );
}
