import { STATUS_LABEL } from "@/lib/status";
import type { AnalysisStatus } from "@/lib/types";

// 기본 검토 라우팅상 담당자 확인이 필요한 상태(claude.md 7절)만 브랜드 점으로 표시하고,
// 색으로 위험도를 매기지 않는다 — 구분은 텍스트 라벨이 한다.
const NEEDS_ATTENTION: Set<AnalysisStatus> = new Set([
  "설명 가능성 있음",
  "설명되지 않은 차이",
  "비교 불가",
  "정보 부족",
]);

export function StatusBadge({ status }: { status: AnalysisStatus }) {
  const attention = NEEDS_ATTENTION.has(status);
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-bg px-3 py-1 text-[13px] font-semibold text-ink-strong">
      <span className={`h-1.5 w-1.5 rounded-full ${attention ? "bg-brand" : "bg-faint"}`} />
      {STATUS_LABEL[status]}
    </span>
  );
}
