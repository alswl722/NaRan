import { StatusBadge } from "@/components/StatusBadge";
import { ComparabilityTable } from "@/components/ComparabilityTable";
import type { ClaimDetail } from "@/lib/types";

/** 장면 3(주장 카드+근거) · 장면 4(대조 결과)를 한 카드에서 함께 보여준다. */
export function ClaimCard({ detail }: { detail: ClaimDetail }) {
  const { claim, comparisons, analyzed } = detail;

  return (
    <div className="rounded-2xl border border-line bg-surface p-5 shadow-card">
      {/* 원문·페이지·메타데이터 — 장면 3 */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[13px] font-semibold text-ink-strong">{claim.metric}</span>
            {claim.scope && (
              <span className="rounded-full bg-bg px-2 py-0.5 text-[11.5px] font-medium text-muted">
                {claim.scope}
              </span>
            )}
            {claim.scope2_method && (
              <span className="rounded-full bg-bg px-2 py-0.5 text-[11.5px] font-medium text-muted">
                {claim.scope2_method}
              </span>
            )}
          </div>
          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[12px] text-faint">
            {claim.organization_boundary && <span>조직경계 {claim.organization_boundary}</span>}
            {claim.geographic_boundary && <span>지역경계 {claim.geographic_boundary}</span>}
            {claim.period_start && claim.period_end && (
              <span>
                {claim.period_start} ~ {claim.period_end}
              </span>
            )}
          </div>
        </div>
        <div className="text-right">
          <div className="text-[17px] font-bold text-ink-strong">
            {claim.value ?? "—"} {claim.unit}
          </div>
          <div className="text-[11px] text-faint">p.{claim.page}</div>
        </div>
      </div>

      <blockquote className="mt-3 rounded-xl bg-bg px-4 py-3 text-[13px] leading-relaxed text-ink">
        “{claim.raw_text}”
      </blockquote>
      <div className="mt-1.5 flex items-center gap-2 text-[11.5px] text-faint">
        <span>{claim.evidence}</span>
        <span className="rounded-full bg-faint/10 px-2 py-0.5 font-medium">
          {claim.extraction_mode === "verified_cache" ? "검증 캐시 사용" : claim.extraction_mode}
        </span>
      </div>

      {/* 대조 결과 — 장면 4 */}
      {!analyzed ? (
        <p className="mt-4 text-[13px] text-faint">아직 분석을 실행하지 않았습니다.</p>
      ) : (
        <div className="mt-4 flex flex-col gap-4">
          {comparisons.map((comp, i) => (
            <div key={i} className="border-t border-line pt-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <StatusBadge status={comp.verdict.status} />
                {comp.verdict.match_type && (
                  <span className="text-[11.5px] text-faint">
                    match_type: {comp.verdict.match_type}
                  </span>
                )}
              </div>

              {comp.public_fact && (
                <div className="mt-2 text-[12.5px] text-muted">
                  공개 데이터: {comp.public_fact.raw_value ?? "—"} {comp.public_fact.unit} ·{" "}
                  <a
                    href={comp.public_fact.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="underline decoration-dotted underline-offset-2 hover:text-brand"
                  >
                    출처
                  </a>{" "}
                  · 조회일 {comp.public_fact.retrieved_at.slice(0, 10)} · 버전{" "}
                  {comp.public_fact.version}
                </div>
              )}

              <p className="mt-2 text-[13px] text-ink">{comp.verdict.explanation}</p>

              {comp.verdict.absolute_difference !== null && (
                <div className="mt-1.5 flex gap-4 text-[13px] text-ink-strong">
                  <span>절대 차이 {comp.verdict.absolute_difference}</span>
                  {comp.verdict.relative_difference_pct !== null && (
                    <span>상대 차이율 {comp.verdict.relative_difference_pct}%</span>
                  )}
                </div>
              )}

              {comp.comparability && (
                <details className="mt-3 group">
                  <summary className="cursor-pointer text-[12.5px] font-medium text-muted select-none">
                    비교 조건 상세 {comp.comparability.comparable ? "" : "— 계산 중단 사유"}
                  </summary>
                  <div className="mt-2">
                    <ComparabilityTable result={comp.comparability} />
                  </div>
                </details>
              )}

              {comp.verdict.review_required && comp.verdict.review_reasons.length > 0 && (
                <div className="mt-2 text-[12px] text-status-possible">
                  검토 필요 사유: {comp.verdict.review_reasons.join(", ")}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
