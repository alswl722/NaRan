import { Fragment } from "react";

/** 텍스트 안에서 알고 있는 값(콤마 유무 두 표기 모두)을 찾아 하이라이트한다.
 * "숫자처럼 보이는 토큰"을 정규식으로 추측하면 연도(2024)·Scope 번호(Scope 1)·
 * 단위 안의 숫자(tCO2eq)까지 걸려 오히려 신뢰할 수 없다 — 대신 우리가 이미
 * 아는 값(claim.value, public_fact.raw_value)만 정확히 찾아 감싼다. */
export function HighlightedText({
  text,
  values,
}: {
  text: string;
  /** 하이라이트할 값 후보 — "71840.290" 같은 원본 문자열을 그대로 넘긴다. */
  values: (string | null | undefined)[];
}) {
  const needles = buildNeedles(values);
  if (needles.length === 0) {
    return <>{text}</>;
  }

  const pattern = new RegExp(
    needles.map((n) => escapeRegExp(n)).join("|"),
    "g",
  );

  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(<Fragment key={key++}>{text.slice(lastIndex, match.index)}</Fragment>);
    }
    parts.push(
      <mark key={key++} className="rounded bg-brand-soft px-0.5 font-semibold text-ink-strong">
        {match[0]}
      </mark>,
    );
    lastIndex = match.index + match[0].length;
    // 빈 매치로 인한 무한 루프 방지
    if (match[0].length === 0) pattern.lastIndex++;
  }
  if (lastIndex < text.length) {
    parts.push(<Fragment key={key++}>{text.slice(lastIndex)}</Fragment>);
  }

  return <>{parts}</>;
}

function buildNeedles(values: (string | null | undefined)[]): string[] {
  const needles = new Set<string>();
  for (const raw of values) {
    if (raw === null || raw === undefined) continue;
    const num = Number(raw);
    if (!Number.isFinite(num)) continue;
    // trailing zero 제거한 순수 숫자 문자열("71840.29")과, 그걸 천 단위로
    // 구분한 표기("71,840.29") 둘 다 후보로 둔다 — 원문 표기를 모르므로.
    const trimmed = raw.includes(".") ? raw.replace(/0+$/, "").replace(/\.$/, "") : raw;
    if (!trimmed || trimmed === "0") continue;
    needles.add(trimmed);
    const [whole, fraction] = trimmed.split(".");
    const withCommas = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    needles.add(fraction ? `${withCommas}.${fraction}` : withCommas);
  }
  // 긴 문자열부터 매칭해야 "71,840"이 "71,840.29" 안에서 먼저 잘리지 않는다.
  return Array.from(needles).sort((a, b) => b.length - a.length);
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
