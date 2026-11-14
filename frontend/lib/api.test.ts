import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, api } from "@/lib/api";
import { safeNextPath } from "@/lib/auth";

type Call = { url: string; init: RequestInit };

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

let calls: Call[];

function mockFetch(...responses: Response[]) {
  calls = [];
  const queue = [...responses];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit = {}) => {
      calls.push({ url, init });
      const next = queue.shift();
      if (!next) throw new Error(`unexpected fetch ${url}`);
      return next;
    }),
  );
}

beforeEach(() => {
  document.cookie = "cb_csrf=nonce.sig; path=/";
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api client", () => {
  it("sends the CSRF token from the cookie on unsafe requests only", async () => {
    mockFetch(jsonResponse(200, { ok: true }), jsonResponse(200, { ok: true }));
    await api.post("/api/v1/x", { a: 1 });
    await api.get("/api/v1/y");
    expect(new Headers(calls[0].init.headers).get("X-CSRF-Token")).toBe("nonce.sig");
    expect(new Headers(calls[1].init.headers).get("X-CSRF-Token")).toBeNull();
    expect(calls[0].init.credentials).toBe("same-origin");
  });

  it("refreshes once on 401 and retries the original request", async () => {
    mockFetch(
      jsonResponse(401, { error: { code: "not_authenticated", message: "Please sign in." } }),
      jsonResponse(200, { message: "Session refreshed." }),
      jsonResponse(200, { user: "ada" }),
    );
    await expect(api.get("/api/v1/auth/me")).resolves.toEqual({ user: "ada" });
    expect(calls.map((c) => c.url)).toEqual(["/api/v1/auth/me", "/api/v1/auth/refresh", "/api/v1/auth/me"]);
  });

  it("throws ApiError when the refresh fails", async () => {
    mockFetch(
      jsonResponse(401, { error: { code: "not_authenticated", message: "Please sign in." } }),
      jsonResponse(401, { error: { code: "not_authenticated", message: "Please sign in." } }),
    );
    const error = await api.get("/api/v1/auth/me").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(401);
    expect(calls).toHaveLength(2);
  });

  it("never tries to refresh after a failed login", async () => {
    mockFetch(jsonResponse(401, { error: { code: "invalid_credentials", message: "Invalid email or password." } }));
    const error = (await api.post("/api/v1/auth/login", {}).catch((e: unknown) => e)) as ApiError;
    expect(error.code).toBe("invalid_credentials");
    expect(calls).toHaveLength(1);
  });

  it("parses field errors from the error envelope", async () => {
    mockFetch(
      jsonResponse(422, {
        error: {
          code: "validation_error",
          message: "Some fields are invalid.",
          request_id: "abc123",
          fields: [{ field: "email", message: "value is not a valid email address" }],
        },
      }),
    );
    const error = (await api.post("/api/v1/auth/register", {}).catch((e: unknown) => e)) as ApiError;
    expect(error.fields).toEqual([{ field: "email", message: "value is not a valid email address" }]);
    expect(error.requestId).toBe("abc123");
  });
});

describe("safeNextPath", () => {
  it.each([
    ["/settings", "/settings"],
    ["/dashboard?tab=1", "/dashboard?tab=1"],
    [null, "/dashboard"],
    ["https://evil.example", "/dashboard"],
    ["//evil.example", "/dashboard"],
    ["/\\evil.example", "/dashboard"],
  ])("%s -> %s", (input, expected) => {
    expect(safeNextPath(input)).toBe(expected);
  });
});
