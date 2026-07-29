"use client";

import { useState } from "react";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { ReviewAction, ReviewRecord } from "@/lib/types";

const ACTIONS: ReviewAction[] = ["추가 자료 요청", "검토 완료", "보류"];

export function HitlPanel({
  caseId,
  history,
  onHistoryChange,
}: {
  caseId: string;
  history: ReviewRecord[];
  onHistoryChange: (next: ReviewRecord[]) => void;
}) {
  const [action, setAction] = useState<ReviewAction>("추가 자료 요청");
  const [note, setNote] = useState("");
  const [reviewer, setReviewer] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastQuestion, setLastQuestion] = useState<string | null>(null);

  async function submit() {
    if (!reviewer.trim() || !note.trim()) {
      setError("검토자와 메모를 입력해 주세요.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const created = await apiPost<ReviewRecord>("/reviews", {
        case_id: caseId,
        action,
        note,
        reviewer,
      });
      setLastQuestion(created.follow_up_question ?? null);
      const refreshed = await apiGet<ReviewRecord[]>(`/reviews/${caseId}/history`);
      onHistoryChange(refreshed);
      setNote("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "조치 저장에 실패했습니다");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="rounded-2xl border border-line bg-surface p-5 shadow-card">
      <h2 className="text-[15px] font-bold text-ink-strong">담당자 조치</h2>
      <p className="mt-1 text-[12.5px] text-faint">
        AI 분석 결과는 여기서 바뀌지 않습니다. 담당자 조치는 별도로 이력에 남습니다.
      </p>

      <div className="mt-4 flex flex-col gap-3">
        <div className="flex gap-2">
          {ACTIONS.map((a) => (
            <button
              key={a}
              type="button"
              onClick={() => setAction(a)}
              className={`rounded-full px-3.5 py-1.5 text-[13px] font-semibold transition-colors ${
                action === a
                  ? "bg-brand text-ink-strong"
                  : "bg-bg text-muted hover:bg-brand-soft"
              }`}
            >
              {a}
            </button>
          ))}
        </div>

        <input
          value={reviewer}
          onChange={(e) => setReviewer(e.target.value)}
          placeholder="검토자"
          className="rounded-xl border border-line bg-bg px-3.5 py-2 text-[13.5px] outline-none focus:border-brand"
        />
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="메모"
          rows={3}
          className="resize-none rounded-xl border border-line bg-bg px-3.5 py-2 text-[13.5px] outline-none focus:border-brand"
        />

        {error && <p className="text-[12.5px] text-status-unexplained">{error}</p>}

        <button
          type="button"
          onClick={submit}
          disabled={submitting}
          className="self-start rounded-xl bg-brand px-4 py-2 text-[13.5px] font-semibold text-ink-strong transition-transform hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting ? "저장 중…" : "조치 저장"}
        </button>

        {lastQuestion && (
          <div className="rounded-xl bg-brand-soft px-4 py-3 text-[13px] text-ink-strong">
            <div className="mb-1 text-[11.5px] font-semibold text-muted">질문 초안</div>
            {lastQuestion}
          </div>
        )}
      </div>

      {history.length > 0 && (
        <div className="mt-5 border-t border-line pt-4">
          <h3 className="text-[12.5px] font-semibold text-muted">감사 이력</h3>
          <ol className="mt-2 flex flex-col gap-2">
            {history.map((h) => (
              <li key={h.id} className="text-[12.5px] text-ink">
                <div className="flex flex-wrap items-baseline gap-x-2">
                  <span className="font-semibold text-ink-strong">{h.action}</span>
                  {h.previous_action && (
                    <span className="text-faint">이전 조치 · {h.previous_action}</span>
                  )}
                </div>
                <div className="text-faint">
                  {h.reviewer} · {formatDateTime(h.processed_at)}
                </div>
                <div className="mt-0.5 text-ink">{h.note}</div>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
