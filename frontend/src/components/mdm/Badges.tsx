import type { Domain, SearchResult } from "@/lib/api";

const DOMAIN_STYLES: Record<Domain, string> = {
  Party: "bg-purple-500/10 text-purple-700 dark:text-purple-400",
  Account: "bg-blue-500/10 text-blue-700 dark:text-blue-400",
  Supplier: "bg-amber-500/10 text-amber-700 dark:text-amber-400",
  Location: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
};

export function DomainBadge({ domain }: { domain: Domain }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${DOMAIN_STYLES[domain]}`}
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
