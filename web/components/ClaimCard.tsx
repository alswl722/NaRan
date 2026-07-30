"use client";

import { StatusBadge } from "@/components/StatusBadge";
import { ComparabilityTable } from "@/components/ComparabilityTable";
import { HighlightedText } from "@/components/HighlightedText";
import { TraceTimeline } from "@/components/TraceTimeline";
import {
  explanationLabel,
  extractionModeLabel,
  reviewReasonLabel,
} from "@/lib/labels";
import {
  formatDateOnly,
  formatDateRange,
  formatDateTime,
  formatDecimal,
  formatValueWithUnit,
  publicFactSentence,
} from "@/lib/format";
import type { ClaimDetail, RunSummary, TraceEvent } from "@/lib/types";

type RunWithTrace = { run: RunSummary; trace: TraceEvent[] };

type ScopeField = { label: string; value: string };

/** Scope·조직경계·지역경계·기간처럼 "동일 범위인지" 판단에 쓰이는 값 —
 * 알약형 배지로 나열하면 어떤 값이 어떤 항목인지 라벨이 안 보였다.
 * 라벨-값 칼럼으로 늘어놓아 조건별로 정확히 대조할 수 있게 한다. */
function ScopeFields({ fields }: { fields: ScopeField[] }) {
  if (fields.length === 0) return null;
  return (
    <div
      data-testid="scope-fields"
      className="mt-2 flex overflow-x-auto border border-line bg-bg/40"
    >
      {fields.map((f) => (
        <div
          key={f.label}
          className={`shrink-0 border-r border-line px-3 py-2 last:border-r-0 ${
            f.label === "기간" ? "min-w-[165px] flex-[1.6]" : "min-w-[80px] flex-1"
          }`}
        >
          <div className="text-[10.5px] font-semibold text-faint">{f.label}</div>
          <div className="mt-0.5 whitespace-nowrap text-[11.5px] font-medium text-ink-strong">
            {f.value}
          </div>
        </div>
      ))}
    </div>
  );
}

/** 카드 안의 섹션 구분 라벨 — 근거 / 대조 결과 / 트레이스처럼 정보 종류가
 * 다른 블록의 경계를 여백만으로는 구분하기 어려워 소제목을 둔다. */
function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-2 text-[11px] font-bold tracking-wide text-muted uppercase">
      {children}
    </div>
  );
}

/** details 토글 공통 헤더 — 배경 있는 칩 + 회전 화살표로 펼침 가능한 요소임을
 * 뚜렷하게 드러낸다. 기존엔 11.5px 옅은 회색 텍스트뿐이라 눈에 잘 안 띄었다. */
function ToggleSummary({ children }: { children: React.ReactNode }) {
  return (
    <summary className="flex cursor-pointer list-none items-center gap-1.5 rounded-sm bg-bg px-3 py-1.5 text-[12.5px] font-semibold text-muted select-none hover:bg-brand-soft hover:text-ink-strong">
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

/** details를 펼쳤을 때 하단 내용이 결과 패널 밖으로 가려지는 경우에만
 * 가장 가까운 세로 스크롤 영역을 필요한 만큼 이동한다. */
function revealExpandedDetails(event: React.SyntheticEvent<HTMLDetailsElement>) {
  const details = event.currentTarget;
  if (!details.open) return;

  requestAnimationFrame(() => {
    let scrollParent: HTMLElement | null = details.parentElement;
    while (scrollParent) {
      const overflowY = window.getComputedStyle(scrollParent).overflowY;
      if (
        (overflowY === "auto" || overflowY === "scroll") &&
        scrollParent.scrollHeight > scrollParent.clientHeight
      ) {
        break;
      }
      scrollParent = scrollParent.parentElement;
    }

    const detailsBottom = details.getBoundingClientRect().bottom;
    const visibleBottom = scrollParent
      ? scrollParent.getBoundingClientRect().bottom
      : window.innerHeight;
    const hiddenHeight = detailsBottom - visibleBottom + 16;
    if (hiddenHeight <= 0) return;

    if (scrollParent) {
      scrollParent.scrollBy({ top: hiddenHeight, behavior: "smooth" });
    } else {
      window.scrollBy({ top: hiddenHeight, behavior: "smooth" });
    }
  });
}

/** 장면 3(주장 카드+근거) · 장면 4(대조 결과)를 한 카드에서 함께 보여준다.
 * 원문 PDF는 좌측 PdfPanel이 상시 노출하므로, 이 카드는 판정 결과 대조에
 * 집중한다. 카드를 클릭하면 좌측 PDF가 이 claim의 페이지·좌표로 동기화된다.
 * 트레이스는 이 claim을 다룬 실행(run)만 골라 카드 안에 그대로 붙인다 —
 * 별도 섹션으로 떼어두면 어떤 판정의 트레이스인지 매번 라벨로 되짚어야 했다. */
export function ClaimCard({
  detail,
  runs = [],
  isActive = false,
  onSelect,
}: {
  detail: ClaimDetail;
  runs?: RunWithTrace[];
  /** 좌측 PdfPanel이 현재 이 claim을 보여주고 있는지 — 카드 강조에 쓴다. */
  isActive?: boolean;
  onSelect?: () => void;
}) {
  const { claim, comparisons, analyzed } = detail;
  const evidenceLocations = claim.evidence
    .split(/\s+및\s+/)
    .map((location) => location.trim())
    .filter(Boolean);

  return (
    <div
      role={onSelect ? "button" : undefined}
      tabIndex={onSelect ? 0 : undefined}
      onClick={onSelect}
      onKeyDown={(e) => {
        if (onSelect && (e.key === "Enter" || e.key === " ")) {
          e.preventDefault();
          onSelect();
        }
      }}
      className={`rounded-sm border bg-surface p-5 shadow-card transition ${
        onSelect ? "cursor-pointer text-left" : ""
      } ${isActive ? "border-brand" : "border-transparent"}`}
    >
      {/* 원문·페이지·메타데이터 — 장면 3 */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[13.5px] font-semibold text-ink-strong">{claim.metric}</div>
        </div>
        <div className="shrink-0 text-right">
          <div className="text-[19px] font-bold tabular-nums text-ink-strong">
            {formatValueWithUnit(claim.value, claim.unit)}
          </div>
        </div>
      </div>

      <ScopeFields
        fields={[
          claim.scope ? { label: "Scope", value: claim.scope } : null,
          claim.scope2_method ? { label: "Scope 2 산정 방식", value: claim.scope2_method } : null,
          claim.organization_boundary
            ? { label: "조직경계", value: claim.organization_boundary }
            : null,
          claim.geographic_boundary
            ? { label: "지역경계", value: claim.geographic_boundary }
            : null,
          claim.period_start && claim.period_end
            ? { label: "기간", value: formatDateRange(claim.period_start, claim.period_end) }
            : null,
        ].filter((f): f is ScopeField => f !== null)}
      />

      {/* 근거 — 원문 인용 + 공개 데이터 근거를 하나의 섹션으로 묶는다.
          전체 PDF는 좌측 PdfPanel이 상시 보여주므로, 여기서는 "이 claim이
          어느 문장에서 왔는지"만 텍스트로 짚어준다. */}
      <div className="mt-4">
        <SectionLabel>근거</SectionLabel>
      </div>
      <div className="rounded-sm border border-line">
        <div className="px-4 py-3">
          <div className="text-[11px] font-semibold text-faint">보고서 원문</div>
          <blockquote className="mt-1 line-clamp-2 text-[13px] leading-relaxed text-ink">
            “<HighlightedText text={claim.raw_text} values={[claim.value]} />”
          </blockquote>
        </div>
        {comparisons.length > 0 && comparisons[0].public_fact && (
          <div className="border-t border-line px-4 py-3">
            <div className="text-[11px] font-semibold text-faint">공개 데이터 근거</div>
            <p className="mt-1 text-[13px] leading-relaxed text-ink">
              <HighlightedText
                text={publicFactSentence(comparisons[0].public_fact)}
                values={[comparisons[0].public_fact.raw_value]}
              />
            </p>
          </div>
        )}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line bg-bg/60 px-4 py-3">
          <div className="min-w-0">
            <div className="text-[11px] font-semibold text-faint">근거 위치</div>
            <ul className="mt-1 list-disc space-y-0.5 pl-4 text-[12.5px] leading-relaxed text-muted">
              {evidenceLocations.map((location) => (
                <li key={location}>{location}</li>
              ))}
            </ul>
          </div>
          <span className="shrink-0 rounded-full border border-line bg-surface px-2.5 py-1 text-[11px] font-semibold text-muted">
            {extractionModeLabel(claim.extraction_mode)}
          </span>
        </div>
      </div>

      {/* 대조 결과 — 장면 4 */}
      {!analyzed ? (
        <div className="mt-4">
          <SectionLabel>대조 결과</SectionLabel>
          <p className="text-[13px] text-faint">아직 분석을 실행하지 않았습니다.</p>
        </div>
      ) : (
        <div className="mt-5 flex flex-col gap-5">
          {comparisons.map((comp, i) => {
            const pendingReasons = comp.verdict.review_reasons.filter(
              (reason) =>
                comp.verdict.review_resolutions[reason]?.resolution !== "확인 완료",
            );
            const humanConfirmed =
              comp.verdict.review_required &&
              comp.verdict.review_reasons.length > 0 &&
              pendingReasons.length === 0;
            const showExplanation = comp.verdict.match_type !== "precision_compatible";
            return (
              <section key={i} className={i === 0 ? "" : "border-t border-line pt-5"}>
              <SectionLabel>대조 결과{comparisons.length > 1 ? ` ${i + 1}` : ""}</SectionLabel>

              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge status={comp.verdict.status} />
                {pendingReasons.length > 0 && (
                  <span className="ml-auto inline-flex items-center gap-1.5 text-[12px] font-semibold text-ink-strong">
                    <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-brand" />
                    검토 필요
                  </span>
                )}
                {humanConfirmed && (
                  <span className="ml-auto text-[12px] font-semibold text-muted">
                    담당자 확인 완료
                  </span>
                )}
              </div>

              {/* 보고서 값과 공개 데이터 값을 같은 자리에 놓고 본다 */}
              <div className="mt-3 grid grid-cols-2 border border-line">
                <div className="border-r border-line px-3 py-2.5 text-center">
                  <div className="text-[11px] text-faint">보고서</div>
                  <div className="mt-0.5 text-[16px] font-bold tabular-nums text-ink-strong">
                    {formatValueWithUnit(comp.verdict.claim_raw_value, claim.unit)}
                  </div>
                </div>
                <div className="px-3 py-2.5 text-center">
                  <div className="text-[11px] text-faint">공개 데이터</div>
                  <div className="mt-0.5 text-[16px] font-bold tabular-nums text-ink-strong">
                    {comp.public_fact
                      ? formatValueWithUnit(comp.verdict.public_raw_value, comp.public_fact.unit)
                      : "—"}
                  </div>
                </div>
              </div>

              {showExplanation && (
                <p className="mt-3 text-[13px] leading-relaxed text-ink">
                  {explanationLabel(comp.verdict.explanation)}
                </p>
              )}

              {comp.verdict.absolute_difference !== null && (
                <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-[13.5px] tabular-nums text-ink-strong">
                  <span>
                    수치 차이{" "}
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
                <div className="mt-3 rounded-sm border border-brand/40 bg-brand-soft px-3 py-2.5">
                  <div className="text-[11px] font-semibold text-muted">
                    {humanConfirmed ? "담당자 확인 완료" : "담당자 확인 사항"}
                  </div>
                  <ul className="mt-1 list-disc space-y-0.5 pl-4 text-[12.5px] text-ink">
                    {comp.verdict.review_reasons.map((reason) => (
                      <li key={reason}>
                        {reviewReasonLabel(reason)}
                        {comp.verdict.review_resolutions[reason]?.resolution === "확인 완료" && (
                          <span className="ml-1 text-muted">
                            · {comp.verdict.review_resolutions[reason].reviewer} 확인
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {comp.public_fact && (
                <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-sm border border-line bg-bg/60 px-3 py-2.5">
                  <div>
                    <div className="text-[11px] font-semibold text-faint">공개 데이터 출처</div>
                    <div className="mt-0.5 text-[12px] text-muted">
                      데이터 조회일 {formatDateOnly(comp.public_fact.retrieved_at)}
                    </div>
                  </div>
                  <a
                    href={comp.public_fact.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="shrink-0 rounded-full border border-line bg-surface px-3 py-1.5 text-[11.5px] font-semibold text-ink-strong hover:border-brand"
                  >
                    원문 열기
                  </a>
                </div>
              )}

              {comp.comparability && (
                <details
                  className="mt-3 group"
                  onClick={(e) => e.stopPropagation()}
                  onToggle={revealExpandedDetails}
                >
                  <ToggleSummary>
                    비교 조건 상세
                    {!comp.comparability.comparable && " — 계산을 중단한 사유"}
                  </ToggleSummary>
                  <div className="mt-2">
                    <ComparabilityTable
                      result={comp.comparability}
                      boundaryMapping={comp.boundary_mapping}
                    />
                  </div>
                </details>
              )}
              </section>
            );
          })}

          {runs.length > 0 && (
            <section className="border-t border-line pt-5">
              <SectionLabel>분석 과정</SectionLabel>
              <details className="group" onClick={(e) => e.stopPropagation()}>
                <ToggleSummary>
                  분석 과정 보기 · {formatDateTime(runs[0].run.started_at)}
                  {runs.length > 1 && ` (이전 실행 ${runs.length - 1}건 더 있음)`}
                </ToggleSummary>
                <div className="mt-2">
                  <TraceTimeline events={runs[0].trace} />
                </div>
              </details>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
