import type { ApiErrorBody } from "@nexus/shared-types";

/** Error raised for any non-2xx API response. Carries the backend error code. */
export class ApiError extends Error {
  code: string;
  status: number;
  requestId: string | null;
  details: Record<string, unknown> | null;

  constructor(status: number, code: string, message: string, requestId: string | null = null, details: Record<string, unknown> | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.details = details;
  }
}

async function parseError(res: Response): Promise<ApiError> {
  try {
    const body = (await res.json()) as ApiErrorBody;
    if (body?.error) {
      return new ApiError(res.status, body.error.code, body.error.message, body.error.request_id ?? null, body.error.details ?? null);
    }
  } catch {
    /* fall through */
  }
  if (res.status === 502 || res.status === 503 || res.status === 504) {
    return new ApiError(res.status, "BACKEND_UNAVAILABLE", "The NEXUS API is not reachable. Is the backend running?");
  }
  return new ApiError(res.status, "HTTP_ERROR", `Request failed (${res.status})`);
}

/** Same-origin request; Next.js proxies /api/* to FastAPI. */
export async function api<T>(path: string, init?: RequestInit & { json?: unknown }): Promise<T> {
  const { json, headers, ...rest } = init ?? {};
  let res: Response;
  try {
    res = await fetch(path, {
      ...rest,
      headers: { ...(json !== undefined ? { "Content-Type": "application/json" } : {}), ...headers },
      body: json !== undefined ? JSON.stringify(json) : rest.body,
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "Network error: cannot reach the NEXUS server");
  }
  if (!res.ok) throw await parseError(res);
  const ct = res.headers.get("content-type") ?? "";
  if (ct.includes("application/json")) return (await res.json()) as T;
  return (await res.text()) as unknown as T;
}

export const fetcher = <T>(path: string): Promise<T> => api<T>(path);

export function post<T>(path: string, json?: unknown): Promise<T> {
  return api<T>(path, { method: "POST", json: json ?? {} });
}

export function put<T>(path: string, json: unknown): Promise<T> {
  return api<T>(path, { method: "PUT", json });
}

export function patch<T>(path: string, json: unknown): Promise<T> {
  return api<T>(path, { method: "PATCH", json });
}

export function del<T>(path: string): Promise<T> {
  return api<T>(path, { method: "DELETE" });
}

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return "Unexpected error";
}

export function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}
