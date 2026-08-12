import type { Domain, FieldDiff, PairwiseMatch, SearchResult } from "@/lib/api";

// Styling for domains Relsun ships baseline recognition of. Any other
// domain value (a tenant's own taxonomy) falls back to DOMAIN_FALLBACK_STYLE
// below rather than rendering broken — the set here is a convenience, not a
// constraint on what domain values are valid.
const DOMAIN_STYLES: Record<string, string> = {
  Party: "bg-purple-500/10 text-purple-700 dark:text-purple-400",
  Account: "bg-blue-500/10 text-blue-700 dark:text-blue-400",
  Supplier: "bg-amber-500/10 text-amber-700 dark:text-amber-400",
  Location: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
};
const DOMAIN_FALLBACK_STYLE = "bg-zinc-500/10 text-zinc-700 dark:text-zinc-400";

// Same domain set, expressed as SVG fill classes for the relationship graph.
const DOMAIN_NODE_FILL: Record<string, string> = {
  Party: "fill-purple-500",
  Account: "fill-blue-500",
  Supplier: "fill-amber-500",
  Location: "fill-emerald-500",
};
const DOMAIN_NODE_FALLBACK_FILL = "fill-zinc-400 dark:fill-zinc-500";

export function domainNodeFill(domain: string | null): string {
  return (domain && DOMAIN_NODE_FILL[domain]) || DOMAIN_NODE_FALLBACK_FILL;
}

export function DomainBadge({ domain }: { domain: Domain }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${DOMAIN_STYLES[domain] ?? DOMAIN_FALLBACK_STYLE}`}
    >
      {domain}
    </span>
  );
}

export function MatchBadge({ result }: { result: SearchResult }) {
  if (result.match_type === "Exact") {
    return (
      <span className="inline-flex items-center rounded-full bg-emerald-600 px-2 py-0.5 text-xs font-medium text-white">
        Exact
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-blue-400 px-2 py-0.5 text-xs font-medium text-blue-700 dark:border-blue-500 dark:text-blue-400">
      Similarity
      <span className="text-blue-400 dark:text-blue-500">· {Math.round(result.score * 100)}%</span>
    </span>
  );
}

const VERDICT_STYLES: Record<PairwiseMatch["verdict"], string> = {
  "Likely duplicate": "bg-rose-600 text-white",
  "Possibly related": "border border-amber-400 text-amber-700 dark:border-amber-500 dark:text-amber-400",
  "Likely distinct": "border border-zinc-300 text-zinc-500 dark:border-zinc-700 dark:text-zinc-500",
};

export function VerdictBadge({ verdict }: { verdict: PairwiseMatch["verdict"] }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${VERDICT_STYLES[verdict]}`}>
      {verdict}
    </span>
  );
}

const FIELD_STATUS_STYLES: Record<FieldDiff["status"], string> = {
  match: "",
  partial: "bg-amber-50 dark:bg-amber-950/20",
  conflict: "bg-rose-50 dark:bg-rose-950/20",
};

export function fieldRowClass(status: FieldDiff["status"]) {
  return FIELD_STATUS_STYLES[status];
}
