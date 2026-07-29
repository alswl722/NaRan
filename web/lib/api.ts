/**
 * 백엔드(FastAPI) 호출 래퍼.
 * 타임아웃: 행 걸린 요청은 무한 대기 대신 빠르게 실패로 드러낸다(실패 가시성 —
 * fallback·목업으로 실패를 가리지 않는다, claude.md 14·15절).
 */
const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const DEFAULT_TIMEOUT_MS = 15_000;
/** /cases/{id}/analyze는 규칙 엔진 전체(비교 가능성 검사·대조·트레이스 기록)를 도니 더 길게 허용. */
export const ANALYZE_TIMEOUT_MS = 30_000;

export class ApiError extends Error {
  status: number;
  constructor(path: string, status: number, detail?: string) {
    super(`API ${path} 실패: ${status}${detail ? ` — ${detail}` : ""}`);
    this.status = status;
  }
}

async function parseErrorDetail(res: Response): Promise<string | undefined> {
  try {
    const body = await res.json();
    return typeof body?.detail === "string" ? body.detail : undefined;
  } catch {
    return undefined;
  }
}

export async function apiGet<T>(path: string, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    cache: "no-store",
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!res.ok) {
    throw new ApiError(path, res.status, await parseErrorDetail(res));
  }
  return res.json() as Promise<T>;
}

export async function apiPost<T>(
  path: string,
  body?: unknown,
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    cache: "no-store",
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!res.ok) {
    throw new ApiError(path, res.status, await parseErrorDetail(res));
  }
  return res.json() as Promise<T>;
}

export { BASE_URL };
