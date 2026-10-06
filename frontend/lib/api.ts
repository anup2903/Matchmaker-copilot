import type {
  Candidate,
  ClientDetail,
  ClientSummary,
  MirrorCard,
  MirrorResponse,
  ProfileCheckResult,
  SampleNote,
  SaveFeedbackResponse,
  StructureResponse,
  StructuredSignal,
} from "./types";

// Relative URL: Next.js proxies /api/* to the FastAPI backend (see next.config.mjs).
const BASE = "/api";

export class ApiError extends Error {
  status: number;
  code: string;
  fallbackAvailable: boolean;

  constructor(message: string, status: number, code = "error", fallbackAvailable = false) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.fallbackAvailable = fallbackAvailable;
  }
}

/** Turn any FastAPI error body into a readable message. */
export function extractErrorMessage(body: unknown, fallback: string): { message: string; code: string; fallbackAvailable: boolean } {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const d = detail as { message?: string; code?: string; fallback_available?: boolean };
    return { message: d.message ?? fallback, code: d.code ?? "error", fallbackAvailable: Boolean(d.fallback_available) };
  }
  if (typeof detail === "string") return { message: detail, code: "error", fallbackAvailable: false };
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: string; loc?: (string | number)[] };
    const where = first.loc?.filter((p) => p !== "body").join(".");
    return { message: `${where ? where + ": " : ""}${first.msg ?? "Invalid input"}`, code: "validation_error", fallbackAvailable: false };
  }
  return { message: fallback, code: "error", fallbackAvailable: false };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      cache: "no-store",
    });
  } catch {
    throw new ApiError("Can't reach the Matchmaker Copilot backend. Check that it is running, then retry.", 0, "network_error");
  }
  if (!res.ok) {
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      /* non-JSON error (e.g. proxy 502 while the backend is down) */
    }
    if (res.status >= 500 && body === null) {
      throw new ApiError("The backend is unavailable right now. Retry in a moment.", res.status, "backend_unavailable");
    }
    const { message, code, fallbackAvailable } = extractErrorMessage(body, `Request failed (${res.status}).`);
    throw new ApiError(message, res.status, code, fallbackAvailable);
  }
  return (await res.json()) as T;
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  clients: () => request<ClientSummary[]>("/clients"),
  client: (id: string) => request<ClientDetail>(`/clients/${id}`),
  candidates: () => request<Candidate[]>("/candidates"),
  profileCheck: (client_id: string, candidate_id: string) =>
    post<ProfileCheckResult>("/profile-check", { client_id, candidate_id }),
  sampleNotes: () => request<SampleNote[]>("/feedback/samples"),
  structureFeedback: (client_id: string, rejection_note: string, use_demo_mode = false) =>
    post<StructureResponse>("/feedback/structure", { client_id, rejection_note, use_demo_mode }),
  saveFeedback: (payload: {
    client_id: string;
    rejection_note: string;
    matchmaker_id: string;
    candidate_id: string | null;
    signals: StructuredSignal[];
  }) => post<SaveFeedbackResponse>("/feedback/save", payload),
  health: () => request<{ status: string; database: string; llm_mode: "demo" | "configured" }>("/health"),
  mirror: (clientId: string) => request<MirrorResponse>(`/clients/${clientId}/preference-mirror`),
  confirmMirror: (signalId: string) => post<MirrorCard>(`/preference-mirror/${signalId}/confirm`),
  dismissMirror: (signalId: string) => post<MirrorCard>(`/preference-mirror/${signalId}/dismiss`),
};
