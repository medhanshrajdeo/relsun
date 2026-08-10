export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type Domain = "Party" | "Account" | "Supplier" | "Location";

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
