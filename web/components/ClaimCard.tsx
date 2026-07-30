"use client";

import dynamic from "next/dynamic";
import { useState } from "react";
import { StatusBadge } from "@/components/StatusBadge";
import { ComparabilityTable } from "@/components/ComparabilityTable";
import { HighlightedText } from "@/components/HighlightedText";
import { TraceTimeline } from "@/components/TraceTimeline";
import { extractionModeLabel, matchTypeLabel } from "@/lib/labels";
import {
  formatDateOnly,
  formatDateRange,
  formatDateTime,
  formatDecimal,
  formatValueWithUnit,
  publicFactSentence,
} from "@/lib/format";
import type { ClaimDetail, RunSummary, TraceEvent } from "@/lib/types";

// pdf.js는 브라우저 전용 API(DOMMatrix 등)에 의존해 서버에서 임포트하면
// 깨진다 — 펼친 시점에만, 클라이언트에서만 로드한다.
const PdfViewer = dynamic(
  () => import("@/components/PdfViewer").then((m) => m.PdfViewer),
  { ssr: false },
);

type RunWithTrace = { run: RunSummary; trace: TraceEvent[] };

/** details 토글 공통 헤더 — 배경 있는 칩 + 회전 화살표로 펼침 가능한 요소임을
 * 뚜렷하게 드러낸다. 기존엔 11.5px 옅은 회색 텍스트뿐이라 눈에 잘 안 띄었다. */
function ToggleSummary({ children }: { children: React.ReactNode }) {
  return (
    <summary className="flex cursor-pointer list-none items-center gap-1.5 rounded-full bg-bg px-3 py-1.5 text-[12.5px] font-semibold text-muted select-none hover:bg-brand-soft hover:text-ink-strong">
      <svg
        className="h-3 w-3 shrink-0 transition-transform group-open:rotate-90"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M9 18l6-6-6-6" />
      </svg>
      {children}
    </summary>
  );
}

/** 장면 3(주장 카드+근거) · 장면 4(대조 결과)를 한 카드에서 함께 보여준다.
 * 담당자가 스캔하듯 훑을 수 있도록, 판단에 필요한 정보(상태·나란히 비교·검토 필요
 * 여부)만 항상 펼쳐두고, 원문·근거·트레이스 같은 부가 정보는 접어서 숨긴다.
 * 트레이스는 이 claim을 다룬 실행(run)만 골라 카드 안에 그대로 붙인다 —
 * 별도 섹션으로 떼어두면 어떤 판정의 트레이스인지 매번 라벨로 되짚어야 했다. */
export function ClaimCard({
  detail,
  runs = [],
  pdfAvailable = false,
}: {
  detail: ClaimDetail;
  runs?: RunWithTrace[];
  /** GET /reports/{report_id}/pdf/meta 결과 — 상위에서 사례당 한 번만 조회해 내려준다. */
  pdfAvailable?: boolean;
}) {
  const { claim, comparisons, analyzed } = detail;
  const [pdfOpen, setPdfOpen] = useState(false);

  function togglePdf() {
    setPdfOpen((open) => !open);
  }

  const metaLine = [
    claim.organization_boundary,
    claim.geographic_boundary,
    claim.period_start && claim.period_end ? formatDateRange(claim.period_start, claim.period_end) : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="rounded-2xl bg-surface p-5 shadow-card">
      {/* 원문·페이지·메타데이터 — 장면 3 */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-1.5 text-[13.5px]">
            <span className="font-semibold text-ink-strong">{claim.metric}</span>
            {claim.scope && <span className="text-muted">· {claim.scope}</span>}
            {claim.scope2_method && <span className="text-muted">· {claim.scope2_method}</span>}
          </div>
          {metaLine && <div className="mt-0.5 text-[11.5px] text-faint">{metaLine}</div>}
        </div>
        <div className="shrink-0 text-right">
          <div className="text-[19px] font-bold tabular-nums text-ink-strong">
            {formatValueWithUnit(claim.value, claim.unit)}
          </div>
          <div className="text-[11px] text-faint">보고서 p.{claim.page}</div>
        </div>
      </div>

      <details className="mt-3 group">
        <ToggleSummary>원문 나란히 보기</ToggleSummary>
        <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div className="rounded-xl bg-bg px-4 py-3">
            <div className="mb-1.5 flex items-center justify-between gap-2 text-[11px] font-semibold text-faint">
              <span>보고서 원문 · p.{claim.page}</span>
              {pdfAvailable ? (
                <button
                  type="button"
                  onClick={togglePdf}
                  className="shrink-0 rounded-full bg-brand-soft px-2 py-0.5 text-[11px] font-semibold text-ink-strong hover:opacity-80"
                >
                  {pdfOpen ? "원문 PDF 접기" : "원문 PDF 보기"}
                </button>
              ) : (
                <span className="shrink-0 text-faint">원문 PDF 없음 (합성 사례)</span>
              )}
            </div>
            <blockquote className="text-[13px] leading-relaxed text-ink">
              “<HighlightedText text={claim.raw_text} values={[claim.value]} />”
            </blockquote>
          </div>
          <div className="rounded-xl bg-bg px-4 py-3">
            <div className="mb-1.5 text-[11px] font-semibold text-faint">공개 데이터 근거</div>
            {comparisons.length > 0 && comparisons[0].public_fact ? (
              <p className="text-[13px] leading-relaxed text-ink">
                <HighlightedText
                  text={publicFactSentence(comparisons[0].public_fact)}
                  values={[comparisons[0].public_fact.raw_value]}
                />
              </p>
            ) : (
              <p className="text-[13px] text-faint">아직 대조된 공개 데이터가 없습니다.</p>
            )}
          </div>
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11.5px] text-faint">
          <span>{claim.evidence}</span>
          <span>{extractionModeLabel(claim.extraction_mode)}</span>
        </div>

        {pdfOpen && (
          <div className="mt-3">
            <PdfViewer
              reportId={claim.report_id}
              initialPage={claim.page}
              claimId={claim.id}
            />
          </div>
        )}
      </details>

      {/* 대조 결과 — 장면 4 */}
      {!analyzed ? (
        <p className="mt-4 text-[13px] text-faint">아직 분석을 실행하지 않았습니다.</p>
      ) : (
        <div className="mt-4 flex flex-col gap-4">
          {comparisons.map((comp, i) => (
            <div key={i} className={i === 0 ? "" : "border-t border-line pt-4"}>
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge status={comp.verdict.status} />
                {matchTypeLabel(comp.verdict.match_type) && (
                  <span className="text-[12px] text-faint">
                    {matchTypeLabel(comp.verdict.match_type)}
                  </span>
                )}
                {comp.verdict.review_required && comp.verdict.review_reasons.length > 0 && (
                  <span className="ml-auto inline-flex items-center gap-1.5 text-[12px] font-semibold text-ink-strong">
                    <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-brand" />
                    검토 필요
                  </span>
                )}
              </div>

              {/* 나란히 — 보고서 값과 공개 데이터 값을 같은 자리에 놓고 본다 */}
              <div className="mt-3 grid grid-cols-[1fr_auto_1fr] items-center gap-2.5">
                <div className="rounded-xl bg-bg px-3 py-2.5 text-center">
                  <div className="text-[11px] text-faint">보고서</div>
                  <div className="mt-0.5 text-[16px] font-bold tabular-nums text-ink-strong">
                    {formatValueWithUnit(comp.verdict.claim_raw_value, claim.unit)}
                  </div>
                </div>
                <span className="text-[12px] font-semibold text-faint">나란히</span>
                <div className="rounded-xl bg-bg px-3 py-2.5 text-center">
                  <div className="text-[11px] text-faint">공개 데이터</div>
                  <div className="mt-0.5 text-[16px] font-bold tabular-nums text-ink-strong">
                    {comp.public_fact
                      ? formatValueWithUnit(comp.verdict.public_raw_value, comp.public_fact.unit)
                      : "—"}
                  </div>
                </div>
              </div>

              <p className="mt-3 text-[13px] leading-relaxed text-ink">{comp.verdict.explanation}</p>

              {comp.verdict.absolute_difference !== null && (
                <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-[13.5px] tabular-nums text-ink-strong">
                  <span>
                    절대 차이{" "}
                    <strong>{formatValueWithUnit(comp.verdict.absolute_difference, claim.unit)}</strong>
                  </span>
                  {comp.verdict.relative_difference_pct !== null && (
                    <span>
                      상대 차이율{" "}
                      <strong>{formatDecimal(comp.verdict.relative_difference_pct)}%</strong>
                    </span>
                  )}
                </div>
              )}

              {comp.verdict.review_required && comp.verdict.review_reasons.length > 0 && (
                <p className="mt-2 text-[12px] text-muted">
                  {comp.verdict.review_reasons.join(" · ")}
                </p>
              )}

              {comp.public_fact && (
                <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11.5px] text-faint">
                  <a
                    href={comp.public_fact.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="underline decoration-dotted underline-offset-2 hover:text-brand"
                  >
                    출처 보기
                  </a>
                  <span>조회일 {formatDateOnly(comp.public_fact.retrieved_at)}</span>
                  <span>버전 {comp.public_fact.version}</span>
                </div>
              )}

              {comp.comparability && (
                <details className="mt-3 group">
                  <ToggleSummary>
                    비교 조건 상세
                    {!comp.comparability.comparable && " — 계산을 중단한 사유"}
                  </ToggleSummary>
                  <div className="mt-2">
                    <ComparabilityTable result={comp.comparability} />
                  </div>
                </details>
              )}
            </div>
          ))}

          {runs.length > 0 && (
            <details className="border-t border-line pt-4 group">
              <ToggleSummary>
                트레이스 보기 · {formatDateTime(runs[0].run.started_at)}
                {runs.length > 1 && ` (이전 실행 ${runs.length - 1}건 더 있음)`}
              </ToggleSummary>
              <div className="mt-2">
                <TraceTimeline events={runs[0].trace} />
              </div>
            </details>
          )}
        </div>
      )}
    </div>
  );
}
