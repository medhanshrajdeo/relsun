// "same-origin" (rather than an empty string) is the deliberate way to say
// "call this page's own origin, no backend host prefix" — Next.js's build
// silently treats an *empty* NEXT_PUBLIC_ value as unset and falls through
// to hardcoded defaults regardless of how the empty string is supplied
// (shell env var, .env.production with a blank value), so an empty string
// can't be used as the "same origin" signal here.
const rawApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
export const API_BASE_URL = rawApiBaseUrl === "same-origin" ? "" : rawApiBaseUrl ?? "http://localhost:8000";

// Module-level, not React state: api.ts is a plain fetch layer with no
// component of its own, so the current session token/401 handler live
// here as module state and lib/auth.tsx's AuthProvider is the only thing
// that ever calls the setters below.
let authToken: string | null = null;
let onUnauthorized: (() => void) | null = null;

export function setAuthToken(token: string | null) {
  authToken = token;
}

export function setUnauthorizedHandler(fn: (() => void) | null) {
  onUnauthorized = fn;
}

// Every authenticated call in this file goes through here so the bearer
// token and the "session died, bounce to /login" behavior are handled in
// exactly one place rather than repeated at each call site.
async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  // Not the standard `Authorization` header: Databricks Apps' own gateway
  // reserves that header for its own OAuth session and strips/rejects
  // anything else in it before the request reaches the backend — see the
  // matching comment in app/deps.py for how this was discovered.
  if (authToken) headers.set("X-Relsun-Token", authToken);
  const res = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  if (res.status === 401) onUnauthorized?.();
  return res;
}

export type AuthUser = {
  id: number;
  username: string;
  display_name: string;
  role: string | null;
};

export async function login(username: string, password: string): Promise<{ token: string; user: AuthUser }> {
  const res = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `Login failed: ${res.status}`);
  }
  return res.json();
}

export async function logout(): Promise<void> {
  await apiFetch("/auth/logout", { method: "POST" }).catch(() => {});
}

export async function fetchCurrentUser(): Promise<AuthUser> {
  const res = await apiFetch("/auth/me");
  if (!res.ok) throw new Error(`Not authenticated: ${res.status}`);
  return res.json();
}

// Not a fixed enum on purpose: Relsun has no baked-in domain taxonomy, each
// tenant's own loaded data defines what domains exist. Use listDomains() to
// discover what's actually present rather than assuming a fixed set.
export type Domain = string;

export async function listDomains(): Promise<Domain[]> {
  const res = await apiFetch("/domains");
  if (!res.ok) throw new Error(`Failed to load domains: ${res.status}`);
  return res.json();
}

export type MasterRecordDetail = {
  id: number;
  domain: Domain;
  name: string;
  external_id: string | null;
  attributes: Record<string, unknown>;
  created_at: string;
};

export async function getMasterRecord(id: number): Promise<MasterRecordDetail> {
  const res = await apiFetch(`/master-records/${id}`);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `Failed to load record ${id}: ${res.status}`);
  }
  return res.json();
}

export type SearchResult = {
  id: number;
  name: string;
  domain: Domain;
  match_type: "Exact" | "Similarity";
  score: number;
};

export async function searchMasterRecords(
  query: string,
  domain: Domain | null,
  signal: AbortSignal
): Promise<SearchResult[]> {
  const params = new URLSearchParams({ q: query });
  if (domain) params.set("domain", domain);

  const res = await apiFetch(`/search?${params.toString()}`, { signal });
  if (!res.ok) throw new Error(`Search failed: ${res.status}`);
  return res.json();
}

export type CompareRecord = {
  id: number;
  name: string;
  domain: Domain;
  attributes: Record<string, unknown>;
};

export type FieldDiff = {
  key: string;
  label: string;
  values: Record<string, unknown>;
  status: "match" | "partial" | "conflict";
};

export type PairwiseMatch = {
  record_a_id: number;
  record_b_id: number;
  score: number;
  verdict: "Likely duplicate" | "Possibly related" | "Likely distinct";
  signals: Record<string, number | boolean>;
  rationale: string;
};

export type CompareResponse = {
  records: CompareRecord[];
  fields: FieldDiff[];
  pairwise: PairwiseMatch[];
};

export async function compareMasterRecords(ids: number[]): Promise<CompareResponse> {
  const params = new URLSearchParams();
  ids.forEach((id) => params.append("ids", String(id)));

  const res = await apiFetch(`/compare?${params.toString()}`);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `Compare failed: ${res.status}`);
  }
  return res.json();
}

export class CompareSummaryUnavailableError extends Error {}

// Separate from compareMasterRecords on purpose: the deterministic
// comparison above is the source of truth and loads fast; this AI-drafted
// narrative is a slower, optional enrichment fetched independently so it
// never blocks or breaks the page the deterministic data already renders.
export async function fetchCompareSummary(ids: number[]): Promise<string> {
  const params = new URLSearchParams();
  ids.forEach((id) => params.append("ids", String(id)));

  const res = await apiFetch(`/compare/summary?${params.toString()}`);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const message = body?.detail ?? `Summary failed: ${res.status}`;
    if (res.status === 503) throw new CompareSummaryUnavailableError(message);
    throw new Error(message);
  }
  const data = await res.json();
  return data.summary;
}

export type GraphNode = {
  id: number;
  name: string | null;
  domain: Domain | null;
  lei: string | null;
  is_anchor: boolean;
  existing_customer: boolean;
};

export type GraphEdge = {
  source: number;
  target: number;
  type: string;
  properties: Record<string, unknown>;
};

export type GraphResponse = {
  center_id: number;
  nodes: GraphNode[];
  edges: GraphEdge[];
  truncated: boolean;
};

export type ConciergeChatTurn = {
  role: "user" | "assistant";
  content: string;
};

export class ConciergeUnavailableError extends Error {}

export async function sendConciergeChat(
  prompt: string,
  history: ConciergeChatTurn[],
  graphContext?: GraphResponse | null
): Promise<string> {
  const res = await apiFetch("/concierge/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, history, graph_context: graphContext ?? null }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const message = body?.detail ?? `Concierge failed: ${res.status}`;
    if (res.status === 503) throw new ConciergeUnavailableError(message);
    throw new Error(message);
  }
  const data = await res.json();
  return data.response;
}

export type MasterDataRequestStatus = "pending" | "approved" | "rejected" | "published";

export type MasterDataRequest = {
  id: number;
  domain: Domain;
  request_type: "create" | "update" | "delete";
  target_record_id: number | null;
  proposed_attributes: Record<string, unknown> | null;
  status: MasterDataRequestStatus;
  decision_note: string | null;
  submitted_at: string;
  decided_at: string | null;
  submitted_by: AuthUser | null;
  decided_by: AuthUser | null;
};

export async function listRequests(status?: MasterDataRequestStatus): Promise<MasterDataRequest[]> {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  const qs = params.toString();
  const res = await apiFetch(`/requests${qs ? `?${qs}` : ""}`);
  if (!res.ok) throw new Error(`Failed to load requests: ${res.status}`);
  return res.json();
}

async function decideRequest(id: number, action: "approve" | "reject", note?: string): Promise<MasterDataRequest> {
  const res = await apiFetch(`/requests/${id}/${action}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision_note: note ?? null }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `${action} failed: ${res.status}`);
  }
  return res.json();
}

export const approveRequest = (id: number, note?: string) => decideRequest(id, "approve", note);
export const rejectRequest = (id: number, note?: string) => decideRequest(id, "reject", note);

export async function fetchRelationshipGraph(id: number, hops = 2): Promise<GraphResponse> {
  const res = await apiFetch(`/graph/${id}?hops=${hops}`);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `Graph fetch failed: ${res.status}`);
  }
  return res.json();
}
