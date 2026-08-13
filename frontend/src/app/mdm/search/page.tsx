"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Search as SearchIcon, Sparkles, X, GitCompareArrows, ExternalLink, Waypoints } from "lucide-react";
import { listDomains, searchMasterRecords, type Domain, type SearchResult } from "@/lib/api";
import { DomainBadge, MatchBadge } from "@/components/mdm/Badges";

const DEBOUNCE_MS = 300;
const MAX_COMPARE = 4;

function SearchPageSkeleton() {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-zinc-200 px-6 py-4 dark:border-zinc-800">
        <div className="h-5 w-48 animate-pulse rounded bg-zinc-200 dark:bg-zinc-800" />
      </div>
      <div className="flex-1 px-6 py-4">
        <div className="h-24 animate-pulse rounded-lg bg-zinc-100 dark:bg-zinc-900" />
      </div>
    </div>
  );
}

function SearchContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [query, setQuery] = useState(() => searchParams.get("q") ?? "");
  const [domain, setDomain] = useState<Domain | null>(() => searchParams.get("domain"));
  const [availableDomains, setAvailableDomains] = useState<Domain[]>([]);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());

  // Keep the URL in sync with the current search + filter (replace, not
  // push, so typing doesn't spam browser history with an entry per
  // keystroke). This is what lets the graph/compare pages' "back" restore
  // the exact search that was in progress, instead of a blank search box.
  useEffect(() => {
    const params = new URLSearchParams();
    if (query) params.set("q", query);
    if (domain) params.set("domain", domain);
    const qs = params.toString();
    router.replace(qs ? `/mdm/search?${qs}` : "/mdm/search", { scroll: false });
  }, [query, domain, router]);

  useEffect(() => {
    // Filter chips reflect whatever domains this tenant's data actually
    // has — not a fixed list, since different customers' data won't share
    // GLEIF's "Party"-only shape.
    listDomains()
      .then(setAvailableDomains)
      .catch(() => setAvailableDomains([]));
  }, []);

  useEffect(() => {
    const trimmed = query.trim();
    if (!trimmed) {
      setResults([]);
      setLoading(false);
      setError(null);
      return;
    }

    const controller = new AbortController();
    setLoading(true);
    setError(null);

    const timer = setTimeout(() => {
      searchMasterRecords(trimmed, domain, controller.signal)
        .then((data) => {
          setResults(data);
          setLoading(false);
        })
        .catch((err) => {
          if (err.name === "AbortError") return;
          setError("Search failed. Is the backend running?");
          setLoading(false);
        });
    }, DEBOUNCE_MS);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, domain]);

  useEffect(() => {
    setSelected(new Set());
  }, [query, domain]);

  const toggleSelected = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else if (next.size < MAX_COMPARE) {
        next.add(id);
      }
      return next;
    });
  };

  const goToCompare = () => {
    const params = new URLSearchParams();
    selected.forEach((id) => params.append("ids", String(id)));
    router.push(`/mdm/compare?${params.toString()}`);
  };

  const hasQuery = query.trim().length > 0;

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-zinc-200 px-6 py-4 dark:border-zinc-800">
        <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Master Data Search</h1>
        <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">Search across your master records.</p>
      </div>

      <div className="space-y-3 border-b border-zinc-200 px-6 py-4 dark:border-zinc-800">
        <div className="relative">
          <SearchIcon size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by keyword, e.g. Hanger"
            className="w-full rounded-lg border border-zinc-300 bg-white py-2 pl-9 pr-9 text-sm text-zinc-900 outline-none placeholder:text-zinc-400 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
          />
          {query && (
            <button
              onClick={() => setQuery("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300"
              aria-label="Clear search"
            >
              <X size={15} />
            </button>
          )}
        </div>

        <div className="flex items-center gap-1.5">
          <span className="mr-1 text-xs font-medium text-zinc-500 dark:text-zinc-400">Filter:</span>
          <button
            onClick={() => setDomain(null)}
            className={`rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
              domain === null
                ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-700"
            }`}
          >
            All
          </button>
          {availableDomains.map((d) => (
            <button
              key={d}
              onClick={() => setDomain(d)}
              className={`rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
                domain === d
                  ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                  : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-700"
              }`}
            >
              {d}
            </button>
          ))}
        </div>
      </div>

      <div className="scrollbar-hide flex-1 overflow-y-auto px-6 py-4">
        {!hasQuery && (
          <div className="flex h-full flex-col items-center justify-center text-center text-zinc-400 dark:text-zinc-600">
            <SearchIcon size={28} className="mb-3" />
            <p className="text-sm">Start typing to search master data.</p>
          </div>
        )}

        {hasQuery && error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-400">
            {error}
          </div>
        )}

        {hasQuery && !error && !loading && results.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-center text-zinc-400 dark:text-zinc-600">
            <p className="text-sm">
              No matches for <span className="font-medium text-zinc-600 dark:text-zinc-400">&ldquo;{query}&rdquo;</span>
            </p>
            <p className="text-xs">Try a different spelling, or check the domain filter.</p>
            <Link
              href={`/?prompt=${encodeURIComponent(`Create a new Party record named "${query}"`)}`}
              className="mt-1 flex items-center gap-1.5 rounded-full border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-600 transition-colors hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700 dark:border-zinc-800 dark:text-zinc-400 dark:hover:border-blue-900 dark:hover:bg-blue-950/30 dark:hover:text-blue-400"
            >
              <Sparkles size={12} />
              Create &ldquo;{query}&rdquo; as a new Party record
            </Link>
          </div>
        )}

        {hasQuery && results.length > 0 && (
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-zinc-200 text-left text-xs font-medium uppercase tracking-wide text-zinc-500 dark:border-zinc-800 dark:text-zinc-500">
                <th className="w-8 py-2"></th>
                <th className="py-2 pr-4">Entity Name</th>
                <th className="py-2 pr-4">ID</th>
                <th className="py-2 pr-4">Domain</th>
                <th className="py-2 pr-4">Match</th>
                <th className="py-2 pr-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className={loading ? "opacity-50 transition-opacity" : "transition-opacity"}>
              {results.map((result) => (
                <tr
                  key={`${result.domain}-${result.id}`}
                  className="border-b border-zinc-100 hover:bg-zinc-50 dark:border-zinc-900 dark:hover:bg-zinc-900/50"
                >
                  <td className="py-2.5">
                    <input
                      type="checkbox"
                      checked={selected.has(result.id)}
                      onChange={() => toggleSelected(result.id)}
                      disabled={!selected.has(result.id) && selected.size >= MAX_COMPARE}
                      title={!selected.has(result.id) && selected.size >= MAX_COMPARE ? `Compare up to ${MAX_COMPARE} records at a time` : undefined}
                      className="rounded border-zinc-300 disabled:cursor-not-allowed disabled:opacity-40 dark:border-zinc-700"
                    />
                  </td>
                  <td className="py-2.5 pr-4 font-medium text-zinc-900 dark:text-zinc-100">{result.name}</td>
                  <td className="py-2.5 pr-4 font-mono text-xs text-zinc-500 dark:text-zinc-500">{result.id}</td>
                  <td className="py-2.5 pr-4">
                    <DomainBadge domain={result.domain} />
                  </td>
                  <td className="py-2.5 pr-4">
                    <MatchBadge result={result} />
                  </td>
                  <td className="py-2.5 pr-4">
                    <div className="flex items-center justify-end gap-1 text-zinc-400">
                      <button
                        onClick={() => router.push(`/mdm/graph?id=${result.id}`)}
                        title="View relationship graph"
                        className="rounded-md p-1.5 hover:bg-zinc-100 hover:text-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-300"
                      >
                        <Waypoints size={15} />
                      </button>
                      <button
                        disabled
                        title="Coming in a later phase (Open record)"
                        className="cursor-not-allowed rounded-md p-1.5 hover:bg-zinc-100 dark:hover:bg-zinc-800"
                      >
                        <ExternalLink size={15} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {selected.size >= 2 && (
        <div className="flex items-center justify-between border-t border-zinc-200 bg-zinc-50 px-6 py-3 dark:border-zinc-800 dark:bg-zinc-900">
          <span className="text-sm text-zinc-600 dark:text-zinc-400">{selected.size} records selected</span>
          <button
            onClick={goToCompare}
            className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
          >
            <GitCompareArrows size={15} />
            Compare
          </button>
        </div>
      )}
    </div>
  );
}

export default function MasterDataSearchPage() {
  return (
    <Suspense fallback={<SearchPageSkeleton />}>
      <SearchContent />
    </Suspense>
  );
}
