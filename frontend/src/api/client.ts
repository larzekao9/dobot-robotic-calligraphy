import type {
  Conversion,
  Job,
  JobRequestBody,
  NameIn,
  NameOut,
  Page,
  PathPreview,
  PendingItem,
  PointName,
  RequestItem,
  RobotConfig,
  RobotStatus,
  SyllableIn,
  SyllableOut,
} from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new ApiError(
      "network_error",
      "No se pudo conectar con el servidor. Revisa la conexión e inténtalo de nuevo.",
      0,
    );
  }
  if (!res.ok) {
    let code = "http_error";
    let message = `Error del servidor (${res.status}).`;
    try {
      const body = await res.json();
      if (body?.error?.message) {
        code = String(body.error.code ?? code);
        message = String(body.error.message);
      }
    } catch {
      /* cuerpo no JSON: se usa el mensaje genérico */
    }
    throw new ApiError(code, message, res.status);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const json = (method: string, body?: unknown, headers: HeadersInit = {}): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json", ...headers },
  body: body === undefined ? undefined : JSON.stringify(body),
});

function query(params: Record<string, string | number | boolean | undefined | null>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") q.set(k, String(v));
  }
  const s = q.toString();
  return s ? `?${s}` : "";
}

export function getHealth(): Promise<{ status: string }> {
  return request("/api/health");
}

export function convertName(name: string): Promise<Conversion> {
  return request("/api/names/convert", json("POST", { name }));
}

export function getRequest(id: string): Promise<Conversion> {
  return request(`/api/requests/${id}`);
}

export function listRequests(page: number, q: string): Promise<Page<RequestItem>> {
  return request(`/api/requests${query({ page, page_size: 10, q })}`);
}

export function previewLayout(body: JobRequestBody): Promise<PathPreview> {
  return request("/api/jobs/preview", json("POST", body));
}

export function createJob(body: JobRequestBody): Promise<Job> {
  return request("/api/jobs", json("POST", body));
}

export function listJobs(): Promise<Job[]> {
  return request("/api/jobs");
}

/** `dryRun`: recorre toda la ruta con la pluma arriba, para comprobar alcance y disposición. */
export function startJob(id: string, dryRun = false): Promise<Job> {
  return request(`/api/jobs/${id}/start${dryRun ? "?dry_run=true" : ""}`, { method: "POST" });
}

export function cancelJob(id: string): Promise<Job> {
  return request(`/api/jobs/${id}/cancel`, { method: "POST" });
}

/** Cliente del panel de administración (el servidor puede exigir `X-Admin-Token` si hay `ADMIN_TOKEN`). */
export function adminApi() {
  const h = {};
  return {
    listNames: (page: number, q: string, onlyPending: boolean): Promise<Page<NameOut>> =>
      request(
        `/api/admin/names${query({ page, page_size: 10, q, verified: onlyPending ? false : undefined })}`,
        { headers: h },
      ),
    createName: (body: NameIn): Promise<NameOut> =>
      request("/api/admin/names", json("POST", body, h)),
    updateName: (id: number, body: NameIn): Promise<NameOut> =>
      request(`/api/admin/names/${id}`, json("PUT", body, h)),
    deleteName: (id: number): Promise<void> =>
      request(`/api/admin/names/${id}`, { method: "DELETE", headers: h }),
    verifyName: (id: number, verified: boolean): Promise<NameOut> =>
      request(`/api/admin/names/${id}/verify`, json("POST", { verified }, h)),
    listSyllables: (
      page: number,
      script: string,
      q: string,
    ): Promise<Page<SyllableOut>> =>
      request(`/api/admin/syllables${query({ page, page_size: 15, script, q })}`, { headers: h }),
    createSyllable: (body: SyllableIn): Promise<SyllableOut> =>
      request("/api/admin/syllables", json("POST", body, h)),
    updateSyllable: (id: number, body: SyllableIn): Promise<SyllableOut> =>
      request(`/api/admin/syllables/${id}`, json("PUT", body, h)),
    deleteSyllable: (id: number): Promise<void> =>
      request(`/api/admin/syllables/${id}`, { method: "DELETE", headers: h }),
    pending: (): Promise<PendingItem[]> => request("/api/admin/pending", { headers: h }),
  };
}

/** Cliente del robot. */
export function robotApi() {
  const h = {};
  return {
    getConfig: (): Promise<RobotConfig> => request("/api/robot/config", { headers: h }),
    saveConfig: (cfg: RobotConfig): Promise<RobotConfig> =>
      request("/api/robot/config", json("PUT", cfg, h)),
    status: (): Promise<RobotStatus> => request("/api/robot/status", { headers: h }),
    enable: (): Promise<RobotStatus> => request("/api/robot/enable", { method: "POST", headers: h }),
    drag: (on: boolean): Promise<RobotStatus> =>
      request("/api/robot/drag", json("POST", { on }, h)),
    capture: (point: PointName): Promise<RobotConfig> =>
      request(`/api/robot/capture/${point}`, { method: "POST", headers: h }),
  };
}

export type RobotApi = ReturnType<typeof robotApi>;
export type AdminApi = ReturnType<typeof adminApi>;
