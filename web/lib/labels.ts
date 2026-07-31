import type { MatchType } from "@/lib/types";

/** 화면에 쓸 사람이 읽는 라벨 — 코드 상수(enum 값)를 그대로 노출하지 않는다. */
export const MATCH_TYPE_LABEL: Record<NonNullable<MatchType>, string> = {
  exact: "완전 일치",
  precision_compatible: "표시 자릿수만 다름",
  different: "수치 차이 있음",
};

export function matchTypeLabel(matchType: MatchType): string | null {
  if (!matchType) return null;
  return MATCH_TYPE_LABEL[matchType] ?? matchType;
}

export const EXTRACTION_MODE_LABEL: Record<string, string> = {
  live: "Gemini 실시간 추출",
  verified_cache: "원문 검증 완료",
  fallback: "Gemini 실패 · 검증값 사용",
};

export function extractionModeLabel(mode: string): string {
  return EXTRACTION_MODE_LABEL[mode] ?? mode;
}

const EXPLANATION_LABELS: Record<string, string> = {
  "표시 정밀도 범위 내 정합; 출처의 표시 규칙은 미확인":
    "표시 자릿수 차이로 볼 수 있으나, 공개 데이터의 반올림·절사 기준 확인이 필요합니다.",
  "원본값을 공통단위로 정규화한 결과 완전 일치":
    "두 수치를 같은 단위로 환산한 결과 정확히 일치합니다.",
};

const REVIEW_REASON_LABELS: Record<string, string> = {
  "출처의 수치 표시 규칙 확인 필요": "공개 데이터의 반올림·절사 기준 확인 필요",
  value: "비교할 수치 확인 필요",
  metric: "지표 정보 확인 필요",
  unit: "단위 정보 확인 필요",
  value_basis: "절대량·원단위 기준 확인 필요",
  entity_level: "기업·사업장 단위 확인 필요",
  organization_boundary: "조직경계 확인 필요",
  geographic_boundary: "지역경계 확인 필요",
  scope: "Scope 범위 확인 필요",
  scope2_method: "Scope 2 산정 방식 확인 필요",
  period: "보고기간 확인 필요",
};

export function explanationLabel(explanation: string): string {
  return EXPLANATION_LABELS[explanation] ?? explanation;
}

export function reviewReasonLabel(reason: string): string {
  return REVIEW_REASON_LABELS[reason] ?? reason;
}
