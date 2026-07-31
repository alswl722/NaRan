"use client";

import { useEffect, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import { apiGet, BASE_URL } from "@/lib/api";

// CDN이 아니라 번들에 포함된 worker를 쓴다 — API 키·네트워크 없이 A·B·C가
// 재현돼야 한다는 완료 조건(claude.md)과 같은 이유로, 오프라인에서도 PDF
// 렌더링이 CDN 가용성에 의존하지 않게 한다.
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

const MIN_WIDTH = 360;
const MAX_WIDTH = 1400;
const WIDTH_STEP = 160;
const DEFAULT_WIDTH = 640;

type HighlightBox = {
  found: boolean;
  page?: number;
  x0?: number;
  top?: number;
  x1?: number;
  bottom?: number;
  page_width?: number;
  page_height?: number;
};

/** 카드 안에 인라인으로 펼쳐지는 PDF 뷰어 — 팝업으로 가리지 않고 원문
 * 나란히 대조 영역 바로 아래 이어 붙는다. 확대/축소는 페이지 렌더링
 * 폭(width)을 조절하는 방식이라 별도 CSS transform 없이 선명하게 커진다.
 * claimId가 있으면 GET /reports/{id}/pdf/highlight로 claim.value의 PDF 내
 * 좌표를 조회해 현재 페이지 위에 노란 박스로 겹쳐 그린다. */
export function PdfViewer({
  reportId,
  initialPage,
  claimId,
}: {
  reportId: string;
  initialPage: number;
  claimId?: string;
}) {
  const [numPages, setNumPages] = useState<number | null>(null);
  const [currentPage, setCurrentPage] = useState(initialPage);
  const [width, setWidth] = useState(DEFAULT_WIDTH);
  const [renderedHeight, setRenderedHeight] = useState<number | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [highlight, setHighlight] = useState<HighlightBox | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const viewerRef = useRef<HTMLDivElement | null>(null);
  const scrollViewportRef = useRef<HTMLDivElement | null>(null);
  const widthBeforeFullscreen = useRef(DEFAULT_WIDTH);
  const dragState = useRef({
    active: false,
    pointerId: -1,
    x: 0,
    y: 0,
    scrollLeft: 0,
    scrollTop: 0,
  });

  useEffect(() => {
    function syncFullscreenState() {
      const fullscreen = document.fullscreenElement === viewerRef.current;
      setIsFullscreen(fullscreen);
      if (!fullscreen) setWidth(widthBeforeFullscreen.current);
    }
    document.addEventListener("fullscreenchange", syncFullscreenState);
    return () => document.removeEventListener("fullscreenchange", syncFullscreenState);
  }, []);

  useEffect(() => {
    let alive = true;
    async function loadHighlight() {
      if (!claimId) {
        if (alive) setHighlight(null);
        return;
      }
      try {
        const box = await apiGet<HighlightBox>(
          `/reports/${reportId}/pdf/highlight?claim_id=${encodeURIComponent(claimId)}`,
        );
        if (alive) setHighlight(box);
      } catch {
        if (alive) setHighlight({ found: false });
      }
    }
    void loadHighlight();
    return () => {
      alive = false;
    };
  }, [reportId, claimId]);

  const showOverlay =
    highlight?.found &&
    highlight.page === currentPage &&
    renderedHeight !== null &&
    highlight.page_width &&
    highlight.page_height;

  async function toggleFullscreen() {
    const viewer = viewerRef.current;
    if (!viewer) return;
    if (document.fullscreenElement === viewer) {
      await document.exitFullscreen();
      return;
    }

    widthBeforeFullscreen.current = width;
    setWidth(Math.min(MAX_WIDTH, Math.max(DEFAULT_WIDTH, window.innerWidth - 64)));
    try {
      await viewer.requestFullscreen();
    } catch {
      setWidth(widthBeforeFullscreen.current);
    }
  }

  function startPan(event: React.PointerEvent<HTMLDivElement>) {
    if (event.button !== 0) return;
    const viewport = scrollViewportRef.current;
    if (!viewport) return;
    const canPan =
      viewport.scrollWidth > viewport.clientWidth ||
      viewport.scrollHeight > viewport.clientHeight;
    if (!canPan) return;

    event.preventDefault();
    viewport.setPointerCapture(event.pointerId);
    dragState.current = {
      active: true,
      pointerId: event.pointerId,
      x: event.clientX,
      y: event.clientY,
      scrollLeft: viewport.scrollLeft,
      scrollTop: viewport.scrollTop,
    };
    setIsDragging(true);
  }

  function movePan(event: React.PointerEvent<HTMLDivElement>) {
    const viewport = scrollViewportRef.current;
    const drag = dragState.current;
    if (!viewport || !drag.active || drag.pointerId !== event.pointerId) return;
    event.preventDefault();
    viewport.scrollLeft = drag.scrollLeft - (event.clientX - drag.x);
    viewport.scrollTop = drag.scrollTop - (event.clientY - drag.y);
  }

  function stopPan(event: React.PointerEvent<HTMLDivElement>) {
    const viewport = scrollViewportRef.current;
    const drag = dragState.current;
    if (!drag.active || drag.pointerId !== event.pointerId) return;
    if (viewport?.hasPointerCapture(event.pointerId)) {
      viewport.releasePointerCapture(event.pointerId);
    }
    dragState.current.active = false;
    setIsDragging(false);
  }

  return (
    <div
      ref={viewerRef}
      className={`overflow-hidden border border-line bg-bg ${
        isFullscreen ? "h-screen rounded-none" : "rounded-xl"
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line bg-surface px-3 py-2">
        <span className="text-[13.5px] font-semibold text-ink-strong">
          {numPages ? `p.${currentPage} / ${numPages}` : "불러오는 중…"}
        </span>
        <div className="flex items-center gap-1.5">
          {numPages && (
            <>
              <button
                type="button"
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage <= 1}
                className="rounded-full bg-bg px-2.5 py-1 text-[13.5px] font-semibold text-muted disabled:cursor-not-allowed disabled:opacity-40"
              >
                이전
              </button>
              <button
                type="button"
                onClick={() => setCurrentPage((p) => Math.min(numPages, p + 1))}
                disabled={currentPage >= numPages}
                className="rounded-full bg-bg px-2.5 py-1 text-[13.5px] font-semibold text-muted disabled:cursor-not-allowed disabled:opacity-40"
              >
                다음
              </button>
            </>
          )}
          <span className="mx-1 h-4 w-px bg-line" />
          <button
            type="button"
            onClick={() => setWidth((w) => Math.max(MIN_WIDTH, w - WIDTH_STEP))}
            disabled={width <= MIN_WIDTH}
            aria-label="축소"
            className="grid h-6 w-6 place-items-center rounded-full bg-bg text-[15.5px] font-bold text-muted disabled:cursor-not-allowed disabled:opacity-40"
          >
            −
          </button>
          <span className="w-10 text-center text-[13px] tabular-nums text-faint">
            {Math.round((width / DEFAULT_WIDTH) * 100)}%
          </span>
          <button
            type="button"
            onClick={() => setWidth((w) => Math.min(MAX_WIDTH, w + WIDTH_STEP))}
            disabled={width >= MAX_WIDTH}
            aria-label="확대"
            className="grid h-6 w-6 place-items-center rounded-full bg-bg text-[15.5px] font-bold text-muted disabled:cursor-not-allowed disabled:opacity-40"
          >
            +
          </button>
          <span className="mx-1 h-4 w-px bg-line" />
          <button
            type="button"
            onClick={() => void toggleFullscreen()}
            className="rounded-full bg-bg px-2.5 py-1 text-[13.5px] font-semibold text-muted hover:text-ink-strong"
          >
            {isFullscreen ? "전체화면 종료" : "전체화면"}
          </button>
        </div>
      </div>

      <div
        ref={scrollViewportRef}
        onPointerDown={startPan}
        onPointerMove={movePan}
        onPointerUp={stopPan}
        onPointerCancel={stopPan}
        onDragStart={(event) => event.preventDefault()}
        aria-label="PDF 보기 영역. 확대 후 마우스로 끌어 이동할 수 있습니다."
        className={`overflow-auto p-4 touch-none ${
          isDragging ? "cursor-grabbing select-none" : "cursor-grab"
        } ${
          isFullscreen ? "h-[calc(100vh-45px)]" : "max-h-full"
        }`}
      >
        {loadError ? (
          <p className="p-6 text-center text-[14.5px] text-status-unexplained">
            PDF를 불러오지 못했습니다: {loadError}
          </p>
        ) : (
          <div className="flex min-w-max justify-center">
            <div className="relative inline-block">
              <Document
                file={`${BASE_URL}/reports/${reportId}/pdf`}
                onLoadSuccess={({ numPages }) => setNumPages(numPages)}
                onLoadError={(err) => setLoadError(err.message)}
                loading={<p className="p-6 text-[14.5px] text-faint">PDF 불러오는 중…</p>}
              >
                <Page
                  pageNumber={currentPage}
                  width={width}
                  onRenderError={(err) => setLoadError(err.message)}
                  onRenderSuccess={(page) => setRenderedHeight(page.height)}
                />
              </Document>

              {showOverlay && (
                <div
                  className="pointer-events-none absolute rounded-sm bg-brand/35 ring-2 ring-brand"
                  style={{
                    left: (highlight.x0! / highlight.page_width!) * width,
                    top: (highlight.top! / highlight.page_height!) * renderedHeight!,
                    width:
                      ((highlight.x1! - highlight.x0!) / highlight.page_width!) * width,
                    height:
                      ((highlight.bottom! - highlight.top!) / highlight.page_height!) *
                      renderedHeight!,
                  }}
                />
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
