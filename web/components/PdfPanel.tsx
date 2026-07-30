"use client";

import dynamic from "next/dynamic";
import { StatusBadge } from "@/components/StatusBadge";
import { HighlightedText } from "@/components/HighlightedText";
import type { ClaimDetail } from "@/lib/types";

// pdf.js는 브라우저 전용 API(DOMMatrix 등)에 의존해 서버에서 임포트하면
// 깨진다 — 클라이언트에서만 로드한다.
const PdfViewer = dynamic(
  () => import("@/components/PdfViewer").then((m) => m.PdfViewer),
  { ssr: false },
);

/** 케이스 상세 페이지의 좌측 슬롯 — "나란히" 컨셉의 왼쪽 절반을 맡는다.
 * PdfViewer(순수 PDF 렌더러+좌표 하이라이트)를 감싸서, 어떤 claim을 보여줄지
 * 결정하는 네비게이션과 PDF가 없는 합성 사례의 대체 화면을 담당한다. */
export function PdfPanel({
  activeDetail,
  pdfAvailable,
  claimDetails,
  activeClaimId,
  onSelectClaim,
}: {
  activeDetail: ClaimDetail | undefined;
  pdfAvailable: boolean;
  claimDetails: ClaimDetail[];
  activeClaimId: string | null;
  onSelectClaim: (claimId: string) => void;
}) {
  const activeIndex = claimDetails.findIndex((d) => d.claim.id === activeClaimId);
  const activeComparison = activeDetail?.comparisons[0] ?? null;

  return (
    <div className="flex flex-col overflow-hidden rounded-2xl bg-surface shadow-card lg:sticky lg:top-16 lg:h-[calc(100vh-4rem)]">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3">
        <div className="min-w-0">
          {activeDetail ? (
            <div className="flex flex-wrap items-center gap-1.5 text-[13px]">
              <span className="font-semibold text-ink-strong">{activeDetail.claim.metric}</span>
              {activeDetail.claim.scope && (
                <span className="rounded-full bg-bg px-2.5 py-1 text-[12px] font-semibold text-ink-strong">
                  {activeDetail.claim.scope}
                </span>
              )}
              {activeDetail.analyzed && activeComparison && (
                <StatusBadge status={activeComparison.verdict.status} />
              )}
            </div>
          ) : (
            <span className="text-[13px] text-faint">표시할 주장이 없습니다</span>
          )}
        </div>
        {claimDetails.length > 1 && (
          <div
            className="flex shrink-0 items-center gap-1 rounded-full bg-bg p-1"
            aria-label="배출량 범위 선택"
          >
            {claimDetails.map((detail, index) => {
              const isActive = index === activeIndex;
              const label = detail.claim.scope || detail.claim.metric;
              return (
                <button
                  key={detail.claim.id}
                  type="button"
                  onClick={() => onSelectClaim(detail.claim.id)}
                  aria-pressed={isActive}
                  className={`whitespace-nowrap rounded-full px-2.5 py-1 text-[11px] font-semibold transition-colors ${
                    isActive
                      ? "bg-surface text-ink-strong shadow-sm"
                      : "text-faint hover:text-ink-strong"
                  }`}
                >
                  {label}
                </button>
              );
            })}
          </div>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {!activeDetail ? (
          <p className="p-6 text-center text-[13px] text-faint">표시할 주장이 없습니다.</p>
        ) : pdfAvailable ? (
          <PdfViewer
            key={`${activeDetail.claim.report_id}:${activeDetail.claim.id}`}
            reportId={activeDetail.claim.report_id}
            initialPage={activeDetail.claim.page}
            claimId={activeDetail.claim.id}
          />
        ) : (
          <div className="rounded-xl bg-bg px-4 py-3">
            <p className="text-[12px] font-semibold text-faint">
              원문 PDF 없음 (데모용 합성 사례) · 보고서 원문 발췌
            </p>
            <blockquote className="mt-2 text-[13px] leading-relaxed text-ink">
              “
              <HighlightedText
                text={activeDetail.claim.raw_text}
                values={[activeDetail.claim.value]}
              />
              ”
            </blockquote>
          </div>
        )}
      </div>
    </div>
  );
}
