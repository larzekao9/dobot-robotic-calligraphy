import { vi } from "vitest";

export interface Call {
  method: string;
  path: string;
  search: URLSearchParams;
  body: unknown;
  headers: Headers;
}

type Result = unknown | Response;
export type Handler = (call: Call) => Result | Promise<Result>;

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), { status });
}

export function apiError(code: string, message: string, status: number): Response {
  return jsonResponse({ error: { code, message } }, status);
}

/** Sustituye `fetch` por un servidor falso: rutas `"MÉTODO /ruta"` → respuesta (o `Response`). */
export function mockApi(routes: Record<string, Handler> = {}) {
  const table: Record<string, Handler> = { "GET /api/health": () => ({ status: "ok" }), ...routes };
  const calls: Call[] = [];
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const u = new URL(url);
    const call: Call = {
      method: init?.method ?? "GET",
      path: u.pathname,
      search: u.searchParams,
      body: init?.body ? JSON.parse(String(init.body)) : undefined,
      headers: new Headers(init?.headers),
    };
    calls.push(call);
    const handler = table[`${call.method} ${call.path}`];
    if (!handler) return apiError("not_found", `sin ruta ${call.method} ${call.path}`, 404);
    const out = await handler(call);
    return out instanceof Response ? out : jsonResponse(out);
  });
  vi.stubGlobal("fetch", fetchMock);
  return {
    calls,
    on: (key: string, h: Handler) => {
      table[key] = h;
    },
    callsTo: (key: string) => calls.filter((c) => `${c.method} ${c.path}` === key),
  };
}
