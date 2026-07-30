"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { ReviewAction, ReviewRecord } from "@/lib/types";

const ACTION_INFO: Record<ReviewAction, string> = {
  "추가 자료 요청": "동일한 비교 범위의 자료를 다시 요청합니다",
  "검토 완료": "현재 분석 결과에 대한 담당자 검토를 마칩니다",
  보류: "추가 판단 없이 보류 상태로 둡니다",
};
const ACTIONS = Object.keys(ACTION_INFO) as ReviewAction[];

const REVIEWER_STORAGE_KEY = "naran.reviewer";

export function HitlPanel({
  caseId,
  history,
  onHistoryChange,
  followUpQuestion,
}: {
  caseId: string;
  history: ReviewRecord[];
  onHistoryChange: (next: ReviewRecord[]) => void;
  followUpQuestion?: string | null;
}) {
  const [action, setAction] = useState<ReviewAction>("추가 자료 요청");
  const [note, setNote] = useState("");
  const [reviewer, setReviewer] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 같은 담당자가 반복해서 검토하는 화면이라, 이름은 세션 간에도 남겨둔다.
  useEffect(() => {
    function restoreReviewer() {
      setReviewer(window.localStorage.getItem(REVIEWER_STORAGE_KEY) ?? "");
    }
    restoreReviewer();
  }, []);

  const latest = history.length > 0 ? history[history.length - 1] : null;

  async function submit() {
    if (!reviewer.trim() || !note.trim()) {
      setError("검토자와 메모를 입력해 주세요.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await apiPost<ReviewRecord>("/reviews", {
        case_id: caseId,
        action,
        note,
        reviewer,
      });
      window.localStorage.setItem(REVIEWER_STORAGE_KEY, reviewer);
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
    <div className="rounded-2xl bg-surface p-5 shadow-card">
      <h2 className="text-[15px] font-bold text-ink-strong">담당자 검토 및 조치</h2>
      <p className="mt-1 text-[12.5px] text-faint">
        AI 분석 결과는 여기서 바뀌지 않습니다. 담당자 조치는 별도로 이력에 남습니다.
      </p>

      <div className="mt-3 rounded-xl bg-bg px-3.5 py-2.5 text-[12.5px]">
        <span className="text-faint">현재 상태 · </span>
        {latest ? (
          <span className="font-semibold text-ink-strong">
            {latest.action} ({latest.reviewer} · {formatDateTime(latest.processed_at)})
          </span>
        ) : (
          <span className="font-semibold text-ink-strong">아직 조치 없음</span>
        )}
      </div>

      <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* 왼쪽 — 조치 선택과 입력 */}
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            {ACTIONS.map((a) => (
              <button
                key={a}
                type="button"
                onClick={() => setAction(a)}
                className={`rounded-xl px-3.5 py-2 text-left ${
                  action === a ? "bg-brand" : "bg-bg hover:bg-brand-soft"
                }`}
              >
                <div className="text-[13px] font-semibold text-ink-strong">{a}</div>
                <div className="text-[11.5px] text-muted">{ACTION_INFO[a]}</div>
              </button>
            ))}
          </div>

          {action === "추가 자료 요청" && followUpQuestion && (
            <div className="rounded-xl bg-brand-soft px-3.5 py-3 text-[12.5px] text-ink-strong">
              <div className="mb-1 flex items-center justify-between gap-2 text-[11px] font-semibold text-muted">
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

          <input
            value={reviewer}
            onChange={(e) => setReviewer(e.target.value)}
            placeholder="검토자"
            className="rounded-xl bg-bg px-3.5 py-2 text-[13.5px] outline-none focus:ring-2 focus:ring-brand"
          />
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="메모"
            rows={3}
            className="resize-none rounded-xl bg-bg px-3.5 py-2 text-[13.5px] outline-none focus:ring-2 focus:ring-brand"
          />

          {error && <p className="text-[12.5px] text-status-unexplained">{error}</p>}

          <button
            type="button"
            onClick={submit}
            disabled={submitting}
            className="self-start rounded-xl bg-brand px-4 py-2 text-[13.5px] font-semibold text-ink-strong shadow-card disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? "저장 중…" : "조치 저장"}
          </button>
        </div>

        {/* 오른쪽 — 감사 이력 */}
        <div className="border-t border-line pt-4 lg:border-t-0 lg:border-l lg:pt-0 lg:pl-6">
          <h3 className="text-[12.5px] font-semibold text-muted">감사 이력 · {history.length}건</h3>
          {history.length === 0 ? (
            <p className="mt-2 text-[12.5px] text-faint">아직 기록된 조치가 없습니다.</p>
          ) : (
            <ol className="mt-2 flex max-h-80 flex-col gap-3 overflow-y-auto pr-1">
              {history.map((h) => (
                <li key={h.id} className="text-[12.5px]">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="rounded-full bg-bg px-2.5 py-0.5 font-semibold text-ink-strong">
                      {h.action}
                    </span>
                    {h.previous_action && <span className="text-faint">← {h.previous_action}</span>}
                    <span className="ml-auto text-faint">{formatDateTime(h.processed_at)}</span>
                  </div>
                  <div className="mt-1 text-faint">{h.reviewer}</div>
                  <div className="mt-0.5 text-ink">{h.note}</div>
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>
    </div>
  );
}
