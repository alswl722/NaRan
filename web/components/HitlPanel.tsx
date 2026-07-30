"use client";

import { useState } from "react";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { CURRENT_USER } from "@/lib/currentUser";
import { formatDateTime } from "@/lib/format";
import type {
  ReviewAction,
  ReviewItem,
  ReviewItemHistoryRecord,
  ReviewRecord,
} from "@/lib/types";

const ACTION_INFO: Record<ReviewAction, string> = {
  "추가 자료 요청": "동일한 비교 범위의 자료를 다시 요청합니다",
  "검토 완료": "현재 분석 결과에 대한 담당자 검토를 마칩니다",
  보류: "추가 판단 없이 보류 상태로 둡니다",
};
const ACTIONS = Object.keys(ACTION_INFO) as ReviewAction[];

export function HitlPanel({
  caseId,
  history,
  onHistoryChange,
  followUpQuestion,
  reviewItems = [],
  reviewItemHistory = [],
  onReviewItemsChange,
}: {
  caseId: string;
  history: ReviewRecord[];
  onHistoryChange: (next: ReviewRecord[]) => void;
  followUpQuestion?: string | null;
  reviewItems?: ReviewItem[];
  reviewItemHistory?: ReviewItemHistoryRecord[];
  onReviewItemsChange: () => Promise<void>;
}) {
  const [action, setAction] = useState<ReviewAction>("추가 자료 요청");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [itemSubmitting, setItemSubmitting] = useState<string | null>(null);
  const [itemNotes, setItemNotes] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  const latest = history.length > 0 ? history[history.length - 1] : null;
  const pendingItemCount = reviewItems.filter(
    (item) => item.resolution?.resolution !== "확인 완료",
  ).length;
  const pendingReviewItems = reviewItems.filter(
    (item) => item.resolution?.resolution !== "확인 완료",
  );
  const compactStatus =
    reviewItems.length > 0
      ? pendingItemCount === 0
        ? "모든 확인 완료"
        : `${pendingItemCount}건 확인 필요`
      : latest
        ? `${latest.action} · ${latest.reviewer}`
        : "아직 조치 없음";
  const auditHistory = [
    ...history.map((record) => ({ kind: "case" as const, record })),
    ...reviewItemHistory.map((record) => ({ kind: "item" as const, record })),
  ].sort(
    (a, b) =>
      new Date(b.record.processed_at).getTime() -
      new Date(a.record.processed_at).getTime(),
  );

  async function submit() {
    if (!note.trim()) {
      setError("메모를 입력해 주세요.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await apiPost<ReviewRecord>("/reviews", {
        case_id: caseId,
        action,
        note,
        reviewer: CURRENT_USER.name,
      });
      const refreshed = await apiGet<ReviewRecord[]>(`/reviews/${caseId}/history`);
      onHistoryChange(refreshed);
      setNote("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "조치 저장에 실패했습니다");
    } finally {
      setSubmitting(false);
    }
  }

  async function submitReviewItem(
    item: ReviewItem,
    resolution: "확인 완료" | "추가 자료 요청",
  ) {
    const key = `${item.verdict_id}:${item.reason}`;
    const itemNote = itemNotes[key]?.trim();
    if (!itemNote) {
      setError(`${item.scope} 확인 근거 또는 요청 내용을 입력해 주세요.`);
      return;
    }
    setItemSubmitting(key);
    setError(null);
    try {
      await apiPost("/reviews/items", {
        case_id: caseId,
        verdict_id: item.verdict_id,
        claim_id: item.claim_id,
        review_reason: item.reason,
        resolution,
        note: itemNote,
        reviewer: CURRENT_USER.name,
      });
      setItemNotes((current) => ({ ...current, [key]: "" }));
      await onReviewItemsChange();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "확인 사항 저장에 실패했습니다");
    } finally {
      setItemSubmitting(null);
    }
  }

  return (
    <div className="rounded-sm border border-line bg-surface p-5 shadow-card">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-[16.5px] font-bold text-ink-strong">담당자 검토 및 조치</h2>
        <span className="rounded-full bg-bg px-2.5 py-1 text-[13px] font-semibold text-muted">
          {compactStatus}
        </span>
      </div>
      <p className="mt-1 text-[14px] text-faint">
        AI 분석 결과는 여기서 바뀌지 않습니다. 담당자 조치는 별도로 이력에 남습니다.
      </p>

      {pendingReviewItems.length > 0 && (
        <div className="mt-3 rounded-sm border border-brand/40 bg-brand-soft px-3.5 py-3">
          <div className="text-[13px] font-semibold text-muted">이번 검토에서 확인할 사항</div>
          <div className="mt-2 divide-y divide-brand/20">
            {pendingReviewItems.map((item) => {
              const key = `${item.verdict_id}:${item.reason}`;
              const confirmed = item.resolution?.resolution === "확인 완료";
              return (
                <div key={key} className="py-2.5 first:pt-0 last:pb-0">
                  <div className="flex flex-wrap items-center gap-2 text-[14px]">
                    <span className="font-semibold text-ink-strong">{item.scope}</span>
                    <span className="text-ink">{item.reason_label}</span>
                    <span className="ml-auto text-[13px] font-semibold text-muted">
                      {confirmed
                        ? `확인 완료 · ${item.resolution?.reviewer}`
                        : item.resolution?.resolution ?? "확인 전"}
                    </span>
                  </div>
                  {confirmed ? (
                    <p className="mt-1 text-[13.5px] text-muted">
                      {item.resolution?.note} ·{" "}
                      {item.resolution && formatDateTime(item.resolution.processed_at)}
                    </p>
                  ) : (
                    <div className="mt-2 flex flex-wrap gap-2">
                      <input
                        value={itemNotes[key] ?? ""}
                        onChange={(event) =>
                          setItemNotes((current) => ({
                            ...current,
                            [key]: event.target.value,
                          }))
                        }
                        placeholder="확인 근거 또는 요청 내용"
                        className="min-w-52 flex-1 rounded-sm bg-surface px-3 py-1.5 text-[13.5px] outline-none focus:ring-2 focus:ring-brand"
                      />
                      <button
                        type="button"
                        onClick={() => submitReviewItem(item, "확인 완료")}
                        disabled={itemSubmitting === key}
                        className="rounded-sm border border-line bg-surface px-3 py-1.5 text-[13.5px] font-semibold text-ink-strong disabled:opacity-50"
                      >
                        확인 완료
                      </button>
                      <button
                        type="button"
                        onClick={() => submitReviewItem(item, "추가 자료 요청")}
                        disabled={itemSubmitting === key}
                        className="rounded-sm bg-brand px-3 py-1.5 text-[13.5px] font-semibold text-ink-strong disabled:opacity-50"
                      >
                        추가 자료 요청
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* 왼쪽 — 조치 선택과 입력 */}
        <div className="flex flex-col gap-3">
          <div>
            <div className="mb-1.5 text-[13px] font-semibold text-faint">조치 선택</div>
            <div className="flex flex-wrap gap-1.5">
            {ACTIONS.map((a) => (
              <button
                key={a}
                type="button"
                onClick={() => setAction(a)}
                aria-pressed={action === a}
                className={`rounded-full px-3.5 py-2 text-[13.5px] font-semibold transition-colors ${
                  action === a
                    ? "bg-brand text-ink-strong"
                    : "border border-line bg-surface text-muted hover:border-brand"
                }`}
              >
                {a}
              </button>
            ))}
            </div>
            <p className="mt-1.5 text-[13.5px] text-muted">{ACTION_INFO[action]}</p>
          </div>

          {action === "추가 자료 요청" && followUpQuestion && (
            <div className="rounded-sm bg-brand-soft px-3.5 py-3 text-[14px] text-ink-strong">
              <div className="mb-1 flex items-center justify-between gap-2 text-[13px] font-semibold text-muted">
                <span>AI가 준비해둔 질문 초안</span>
                <button
                  type="button"
                  onClick={() => setNote(followUpQuestion)}
                  className="shrink-0 text-brand underline decoration-dotted underline-offset-2"
                >
                  메모에 채우기
                </button>
              </div>
              {followUpQuestion}
            </div>
          )}

          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="메모"
            rows={3}
            className="resize-none rounded-sm bg-bg px-3.5 py-2 text-[15px] outline-none focus:ring-2 focus:ring-brand"
          />

          {error && <p className="text-[14px] text-status-unexplained">{error}</p>}

          <button
            type="button"
            onClick={submit}
            disabled={submitting}
            className="self-start rounded-sm bg-brand px-4 py-2 text-[15px] font-semibold text-ink-strong shadow-card disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? "저장 중…" : "조치 저장"}
          </button>
        </div>

        {/* 오른쪽 — 감사 이력 */}
        <div className="border-t border-line pt-4 lg:border-t-0 lg:border-l lg:pt-0 lg:pl-6">
          <h3 className="text-[14px] font-semibold text-muted">
            감사 이력 · {auditHistory.length}건
          </h3>
          {auditHistory.length === 0 ? (
            <p className="mt-2 text-[14px] text-faint">아직 기록된 조치가 없습니다.</p>
          ) : (
            <ol className="mt-2 flex max-h-80 flex-col gap-3 overflow-y-auto pr-1">
              {auditHistory.map(({ kind, record }) => {
                const item =
                  kind === "item"
                    ? reviewItems.find(
                        (candidate) =>
                          candidate.verdict_id === record.verdict_id &&
                          candidate.reason === record.review_reason,
                      )
                    : null;
                return (
                <li key={`${kind}:${record.id}`} className="text-[14px]">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="rounded-full bg-bg px-2.5 py-0.5 font-semibold text-ink-strong">
                      {kind === "case" ? record.action : record.resolution}
                    </span>
                    {kind === "case" && record.previous_action && (
                      <span className="text-faint">← {record.previous_action}</span>
                    )}
                    {kind === "item" && (
                      <span className="text-faint">
                        {item?.scope ?? "확인 사항"} ·{" "}
                        {item?.reason_label ?? record.review_reason}
                      </span>
                    )}
                    <span className="ml-auto text-faint">
                      {formatDateTime(record.processed_at)}
                    </span>
                  </div>
                  <div className="mt-1 flex items-center gap-1.5 text-faint">
                    <span className="flex h-5 w-5 items-center justify-center rounded-full bg-brand-soft text-[12px] font-semibold text-ink-strong">
                      {record.reviewer === CURRENT_USER.name
                        ? CURRENT_USER.initials
                        : record.reviewer.slice(0, 1)}
                    </span>
                    <span>{record.reviewer}</span>
                  </div>
                  <div className="mt-0.5 text-ink">{record.note}</div>
                </li>
                );
              })}
            </ol>
          )}
        </div>
      </div>
    </div>
  );
}
