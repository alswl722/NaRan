import type { ComparabilityResult } from "@/lib/types";

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

const STATUS_STYLE: Record<string, string> = {
  일치: "text-status-match bg-status-match/10",
  불일치: "text-status-unexplained bg-status-unexplained/10",
  누락: "text-status-possible bg-status-possible/10",
  "해당 없음": "text-faint bg-faint/10",
};

export function ComparabilityTable({ result }: { result: ComparabilityResult }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-line">
      <table className="w-full min-w-[520px] text-left text-[13px]">
        <thead>
          <tr className="border-b border-line bg-bg text-[12px] text-faint">
            <th className="px-3 py-2 font-medium">조건</th>
            <th className="px-3 py-2 font-medium">주장값</th>
            <th className="px-3 py-2 font-medium">공개값</th>
            <th className="px-3 py-2 font-medium">결과</th>
          </tr>
        </thead>
        <tbody>
          {result.conditions.map((c) => (
            <tr key={c.field} className="border-b border-line last:border-0">
              <td className="px-3 py-2 font-medium text-ink-strong">
                {FIELD_LABEL[c.field] ?? c.field}
              </td>
              <td className="px-3 py-2 text-ink">{c.claim_value ?? "—"}</td>
              <td className="px-3 py-2 text-ink">{c.public_value ?? "—"}</td>
              <td className="px-3 py-2">
                <span
                  className={`inline-block rounded-full px-2 py-0.5 text-[11.5px] font-semibold ${
                    STATUS_STYLE[c.status] ?? "text-faint bg-faint/10"
                  }`}
                >
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
