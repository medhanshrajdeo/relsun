export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// Not a fixed enum on purpose: Relsun has no baked-in domain taxonomy, each
// tenant's own loaded data defines what domains exist. Use listDomains() to
// discover what's actually present rather than assuming a fixed set.
export type Domain = string;

export async function listDomains(): Promise<Domain[]> {
  const res = await fetch(`${API_BASE_URL}/domains`);
  if (!res.ok) throw new Error(`Failed to load domains: ${res.status}`);
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

  const res = await fetch(`${API_BASE_URL}/search?${params.toString()}`, { signal });
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

  const res = await fetch(`${API_BASE_URL}/compare?${params.toString()}`);
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

  const res = await fetch(`${API_BASE_URL}/compare/summary?${params.toString()}`);
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

export async function sendConciergeChat(prompt: string, history: ConciergeChatTurn[]): Promise<string> {
  const res = await fetch(`${API_BASE_URL}/concierge/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, history }),
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
};

export async function listRequests(status?: MasterDataRequestStatus): Promise<MasterDataRequest[]> {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  const qs = params.toString();
  const res = await fetch(`${API_BASE_URL}/requests${qs ? `?${qs}` : ""}`);
  if (!res.ok) throw new Error(`Failed to load requests: ${res.status}`);
  return res.json();
}

async function decideRequest(id: number, action: "approve" | "reject", note?: string): Promise<MasterDataRequest> {
  const res = await fetch(`${API_BASE_URL}/requests/${id}/${action}`, {
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
  const res = await fetch(`${API_BASE_URL}/graph/${id}?hops=${hops}`);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `Graph fetch failed: ${res.status}`);
  }
  return res.json();
}
