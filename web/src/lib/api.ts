// Thin fetch wrapper: same-origin, credentials, CSRF header, JSON parse, typed errors.

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown, message: string) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

// The DashboardCSRFMiddleware sets `dashboard_csrf` as HttpOnly, so JS cannot
// read the cookie. The SPA receives the matching token from /api/me JSON and
// stashes it here; mutating requests echo it as X-CSRF-Token. App.tsx keeps
// this in sync with the useSession query result.
let _csrfToken: string | null = null;

export function setCsrfToken(token: string | null | undefined): void {
  _csrfToken = token ?? null;
}

export function getCsrfToken(): string | null {
  return _csrfToken;
}

type RequestOpts = RequestInit & { json?: unknown };

export async function request<T = unknown>(path: string, opts: RequestOpts = {}): Promise<T> {
  const headers = new Headers(opts.headers);
  if (opts.json !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  if (opts.method && opts.method.toUpperCase() !== "GET" && opts.method.toUpperCase() !== "HEAD") {
    if (_csrfToken) headers.set("X-CSRF-Token", _csrfToken);
  }
  const res = await fetch(path, {
    ...opts,
    headers,
    credentials: "include",
    body: opts.json !== undefined ? JSON.stringify(opts.json) : opts.body,
  });
  const ct = res.headers.get("content-type") ?? "";
  let body: unknown = null;
  if (ct.includes("application/json")) {
    body = await res.json().catch(() => null);
  } else {
    body = await res.text().catch(() => "");
  }
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    if (body && typeof body === "object" && "error" in (body as any)) {
      msg = String((body as any).error);
    }
    throw new ApiError(res.status, body, msg);
  }
  return body as T;
}

export const api = {
  get: <T = unknown>(p: string) => request<T>(p, { method: "GET" }),
  post: <T = unknown>(p: string, json?: unknown) => request<T>(p, { method: "POST", json }),
  put: <T = unknown>(p: string, json?: unknown) => request<T>(p, { method: "PUT", json }),
  patch: <T = unknown>(p: string, json?: unknown) => request<T>(p, { method: "PATCH", json }),
  del: <T = unknown>(p: string) => request<T>(p, { method: "DELETE" }),
};
