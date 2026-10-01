import { afterEach, describe, expect, it, vi } from "vitest";

import { api, ApiError, errorMessage, qs } from "@/lib/api";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("builds query strings and skips empty values", () => {
    expect(qs({ a: 1, b: "", c: null, d: undefined, e: false, f: "x y" })).toBe("?a=1&e=false&f=x+y");
    expect(qs({})).toBe("");
  });

  it("parses structured backend errors", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(422, { error: { code: "VALIDATION_ERROR", message: "Bad input", request_id: "req_1", details: { field: "x" } } })));
    const err = await api("/api/x").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).code).toBe("VALIDATION_ERROR");
    expect((err as ApiError).status).toBe(422);
    expect((err as ApiError).requestId).toBe("req_1");
    expect(errorMessage(err)).toBe("Bad input");
  });

  it("maps a down backend to a clear message without leaking internals", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("<html>Bad gateway</html>", { status: 502 })));
    const err = (await api("/api/x").catch((e: unknown) => e)) as ApiError;
    expect(err.code).toBe("BACKEND_UNAVAILABLE");
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("fetch failed"))));
    const net = (await api("/api/x").catch((e: unknown) => e)) as ApiError;
    expect(net.code).toBe("NETWORK_ERROR");
  });

  it("sends JSON bodies and returns parsed JSON", async () => {
    const spy = vi.fn(async (_url: string, init?: RequestInit) => json(200, { echo: JSON.parse(String(init?.body)) }));
    vi.stubGlobal("fetch", spy);
    const res = await api<{ echo: { a: number } }>("/api/y", { method: "POST", json: { a: 1 } });
    expect(res.echo.a).toBe(1);
    const init = spy.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
    expect(init.cache).toBe("no-store");
  });
});
