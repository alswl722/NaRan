import type { MatchType } from "@/lib/types";

/** 화면에 쓸 사람이 읽는 라벨 — 코드 상수(enum 값)를 그대로 노출하지 않는다. */
export const MATCH_TYPE_LABEL: Record<NonNullable<MatchType>, string> = {
  exact: "완전 일치",
  precision_compatible: "표시 정밀도 범위 내 일치",
  different: "수치 차이 있음",
};

export function matchTypeLabel(matchType: MatchType): string | null {
  if (!matchType) return null;
  return MATCH_TYPE_LABEL[matchType] ?? matchType;
}

export const EXTRACTION_MODE_LABEL: Record<string, string> = {
  live: "실시간 추출",
  verified_cache: "검증된 캐시",
  fallback: "실시간 실패 후 캐시",
};

export function extractionModeLabel(mode: string): string {
  return EXTRACTION_MODE_LABEL[mode] ?? mode;
}
