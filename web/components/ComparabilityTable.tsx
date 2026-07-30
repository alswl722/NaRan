import { formatDecimal } from "@/lib/format";
import type { ComparabilityResult } from "@/lib/types";

/** value 조건만 숫자 — 나머지 필드(scope, unit 등)는 문자열 그대로 둔다. */
function displayValue(field: string, value: string | null): string {
  if (value === null) return "—";
  if (field !== "value") return value;
  return formatDecimal(value);
}

const FIELD_LABEL: Record<string, string> = {
  value: "수치",
  metric: "지표",
  unit: "단위",
  value_basis: "절대량·원단위 기준",
  entity_level: "기업·사업장 단위",
  organization_boundary: "조직경계",
  geographic_boundary: "지역경계",
  scope: "Scope 범위",
  scope2_method: "Scope 2 산정 방식",
  period: "보고기간",
};

// 불일치·누락은 위험이 아니라 "눈여겨볼 지점"이라 브랜드색으로, 나머지는 중립으로 표시한다.
const NEEDS_ATTENTION = new Set(["불일치", "누락"]);

export function ComparabilityTable({ result }: { result: ComparabilityResult }) {
  return (
    <div className="overflow-x-auto rounded-xl bg-bg">
      <table className="w-full min-w-[520px] text-left text-[13px]">
        <thead>
          <tr className="text-[12px] text-faint">
            <th className="px-3 py-2 font-medium">조건</th>
            <th className="px-3 py-2 font-medium">주장값</th>
            <th className="px-3 py-2 font-medium">공개값</th>
            <th className="px-3 py-2 font-medium">결과</th>
          </tr>
        </thead>
        <tbody>
          {result.conditions.map((c) => (
            <tr key={c.field}>
              <td className="px-3 py-2 font-medium text-ink-strong">
                {FIELD_LABEL[c.field] ?? c.field}
              </td>
              <td className="px-3 py-2 tabular-nums text-ink">{displayValue(c.field, c.claim_value)}</td>
              <td className="px-3 py-2 tabular-nums text-ink">{displayValue(c.field, c.public_value)}</td>
              <td className="px-3 py-2">
                <span
                  className={`inline-flex items-center gap-1.5 text-[11.5px] font-semibold ${
                    NEEDS_ATTENTION.has(c.status) ? "text-ink-strong" : "text-faint"
                  }`}
                >
                  {NEEDS_ATTENTION.has(c.status) && (
                    <span className="h-1.5 w-1.5 rounded-full bg-brand" />
                  )}
                  {c.status}
                </span>
                {c.reason && <div className="mt-0.5 text-[11.5px] text-faint">{c.reason}</div>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
