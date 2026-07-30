/**
 * 백엔드가 반환하는 수치 문자열(Decimal → str, 예: "71840.2900000000")을
 * 화면 표시용으로 정리한다. 값 자체는 바꾸지 않는다 — 원본 정밀도는
 * 여전히 API 응답 문자열에 그대로 있고, 이 함수는 순수 표시 포맷팅만
 * 담당한다 (claude.md: 임의로 "반올림"이라 단정하지 않는다 — 여기서도
 * 반올림이 아니라 후행 0 제거 + 천 단위 구분만 한다).
 */
export function formatDecimal(value: string | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const num = Number(value);
  if (!Number.isFinite(num)) return value;

  // 소수부의 의미 없는 후행 0만 제거 — 유효 소수 자릿수는 그대로 둔다.
  const trimmed = value.includes(".") ? value.replace(/0+$/, "").replace(/\.$/, "") : value;
  const [whole, fraction] = trimmed.split(".");
  const withCommas = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return fraction ? `${withCommas}.${fraction}` : withCommas;
}

/** 단위까지 붙여서 "71,840.29 tCO2eq" 형태로 만든다. */
export function formatValueWithUnit(
  value: string | null | undefined,
  unit: string | null | undefined,
): string {
  const formatted = formatDecimal(value);
  if (formatted === "—") return formatted;
  return unit ? `${formatted} ${unit}` : formatted;
}

/** "2024-01-01" ~ "2024-12-31" → "2024.01.01 ~ 2024.12.31" (좀 더 읽기 쉬운 구분자) */
export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  return value.replaceAll("-", ".");
}

export function formatDateRange(
  start: string | null | undefined,
  end: string | null | undefined,
): string {
  if (!start || !end) return "—";
  return `${formatDate(start)} ~ ${formatDate(end)}`;
}

/** ISO datetime → "2026.07.29" (조회일·처리시각 등 날짜만 필요한 곳) */
export function formatDateOnly(iso: string): string {
  return iso.slice(0, 10).replaceAll("-", ".");
}

/** ISO datetime → "2026.07.29 13:40" */
export function formatDateTime(iso: string): string {
  return `${iso.slice(0, 10).replaceAll("-", ".")} ${iso.slice(11, 16)}`;
}

/** PublicFact에는 원문 문장이 없어 필드를 조합해 보고서 원문과 나란히 놓을
 * 수 있는 근거 문장을 합성한다 — "env-info 공개 데이터 · Scope 1 · 71,840
 * tCO2eq (2024.01.01 ~ 2024.12.31)" 형태. */
export function publicFactSentence(fact: {
  raw_value: string | null;
  unit: string | null;
  scope: string | null;
  period_start?: string | null;
  period_end?: string | null;
  source_url: string;
}): string {
  const source = fact.source_url.includes("env-info.kr")
    ? "환경정보공개시스템(env-info) 공개 데이터"
    : fact.source_url.includes("gir.go.kr")
      ? "온실가스종합정보센터(GIR) 공개 데이터"
      : "공개 데이터";
  const parts = [source, fact.scope, formatValueWithUnit(fact.raw_value, fact.unit)].filter(
    Boolean,
  );
  return parts.join(" · ");
}
