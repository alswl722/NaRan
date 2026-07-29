import type { AnalysisStatus } from "@/lib/types";

/**
 * 화면 용어 사전 (claude.md 17절) — 그린워싱·허위·위반 같은 금지 표현을
 * 절대 쓰지 않는다. "비교 불가"는 위험이 아니라 중립 상태로 표기한다.
 */
export const STATUS_LABEL: Record<AnalysisStatus, string> = {
  일치: "일치",
  "설명된 차이": "설명된 차이",
  "설명 가능성 있음": "설명 가능성 있음",
  "설명되지 않은 차이": "설명되지 않은 차이",
  "비교 불가": "비교 불가",
  "정보 부족": "정보 부족",
};

export const STATUS_COLOR_VAR: Record<AnalysisStatus, string> = {
  일치: "var(--color-status-match)",
  "설명된 차이": "var(--color-status-explained)",
  "설명 가능성 있음": "var(--color-status-possible)",
  "설명되지 않은 차이": "var(--color-status-unexplained)",
  "비교 불가": "var(--color-status-not-comparable)",
  "정보 부족": "var(--color-status-insufficient)",
};
