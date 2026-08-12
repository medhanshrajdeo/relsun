"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowLeft, GitCompareArrows, ShieldCheck, Sparkles } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  compareMasterRecords,
  fetchCompareSummary,
  CompareSummaryUnavailableError,
  type CompareResponse,
} from "@/lib/api";
import { DomainBadge, fieldRowClass } from "@/components/mdm/Badges";

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

function ComparePageSkeleton() {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-zinc-200 px-6 py-4 dark:border-zinc-800">
        <div className="h-5 w-40 animate-pulse rounded bg-zinc-200 dark:bg-zinc-800" />
      </div>
      <div className="flex-1 px-6 py-4">
        <div className="h-24 animate-pulse rounded-lg bg-zinc-100 dark:bg-zinc-900" />
      </div>
    </div>
  );
}

function CompareContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const ids = useMemo(
    () =>
      searchParams
        .getAll("ids")
        .map((v) => Number(v))
        .filter((n) => Number.isFinite(n)),
    [searchParams]
  );

  const [data, setData] = useState<CompareResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [summary, setSummary] = useState<string | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [summaryUnavailable, setSummaryUnavailable] = useState(false);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  useEffect(() => {
    if (ids.length < 2) {
      setError("Select at least 2 records from search to compare.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    compareMasterRecords(ids)
      .then((res) => {
        setData(res);
        setLoading(false);
      })
      .catch((err: Error) => {
        setError(err.message || "Compare failed. Is the backend running?");
        setLoading(false);
      });
  }, [ids]);

  // Independent of the deterministic fetch above on purpose — the AI
  // summary is slower (an LLM call) and optional; it shouldn't block or be
  // coupled to the fast, always-available deterministic comparison.
  useEffect(() => {
    if (ids.length < 2) {
      setSummaryLoading(false);
      return;
    }
    setSummaryLoading(true);
    setSummaryUnavailable(false);
    setSummaryError(null);
    fetchCompareSummary(ids)
      .then((text) => {
        setSummary(text);
        setSummaryLoading(false);
      })
      .catch((err: Error) => {
        if (err instanceof CompareSummaryUnavailableError) {
          setSummaryUnavailable(true);
        } else {
          setSummaryError(err.message || "AI summary failed.");
        }
        setSummaryLoading(false);
      });
  }, [ids]);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-zinc-200 px-6 py-4 dark:border-zinc-800">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-1.5 rounded-md p-1.5 text-zinc-500 hover:bg-zinc-100 hover:text-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-300"
          aria-label="Back to search"
        >
          <ArrowLeft size={16} />
        </button>
        <div>
          <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Compare Records</h1>
          <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">
            {data ? `${data.records.length} records` : "Loading…"} · deterministic match analysis + AI-drafted summary
          </p>
        </div>
      </div>

      <div className="scrollbar-hide flex-1 overflow-y-auto px-6 py-5">
        {loading && <ComparePageSkeleton />}

        {!loading && error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-400">
            {error}{" "}
            <Link href="/mdm/search" className="font-medium underline">
              Back to search
            </Link>
          </div>
        )}

        {!loading && !error && data && (
          <div className="space-y-8">
            <section>
              <h2 className="mb-3 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-500">
                <Sparkles size={13} /> AI Summary
              </h2>
              <div className="rounded-lg border border-zinc-200 bg-zinc-50/50 p-4 dark:border-zinc-800 dark:bg-zinc-900/30">
                {summaryLoading && (
                  <div className="flex items-center gap-2 text-sm text-zinc-400 dark:text-zinc-600">
                    <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-500 dark:border-zinc-700 dark:border-t-zinc-400" />
                    Drafting summary…
                  </div>
                )}
                {!summaryLoading && summaryUnavailable && (
                  <p className="text-sm text-zinc-400 dark:text-zinc-600">
                    AI summary isn&apos;t available yet — no Foundry project is configured in this environment.
                  </p>
                )}
                {!summaryLoading && summaryError && (
                  <p className="text-sm text-red-600 dark:text-red-400">{summaryError}</p>
                )}
                {!summaryLoading && summary && (
                  <>
                    <p className="text-sm text-zinc-700 dark:text-zinc-300">{summary}</p>
                    <p className="mt-2 text-xs text-zinc-400 dark:text-zinc-600">
                      AI-drafted from the match analysis below — a draft for review, not a decision. Verify against
                      the data itself before acting on it.
                    </p>
                  </>
                )}
              </div>
            </section>

            <section>
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-500">
                Field Comparison
              </h2>
              <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
                <table className="w-full min-w-max border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-zinc-200 bg-zinc-50 text-left dark:border-zinc-800 dark:bg-zinc-900">
                      <th className="w-40 py-2.5 pl-4 pr-4 text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-500">
                        Field
                      </th>
                      {data.records.map((r) => (
                        <th key={r.id} className="min-w-[180px] py-2.5 pr-4 align-bottom">
                          <div className="font-medium text-zinc-900 dark:text-zinc-100">{r.name}</div>
                          <div className="mt-1">
                            <DomainBadge domain={r.domain} />
                          </div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-b border-zinc-100 dark:border-zinc-900">
                      <td className="py-2 pl-4 pr-4 text-zinc-500 dark:text-zinc-500">ID</td>
                      {data.records.map((r) => (
                        <td key={r.id} className="py-2 pr-4 font-mono text-xs text-zinc-500 dark:text-zinc-500">
                          {r.id}
                        </td>
                      ))}
                    </tr>
                    {data.fields.map((field) => (
                      <tr
                        key={field.key}
                        className={`border-b border-zinc-100 dark:border-zinc-900 ${fieldRowClass(field.status)}`}
                      >
                        <td className="py-2 pl-4 pr-4 text-zinc-500 dark:text-zinc-500">{field.label}</td>
                        {data.records.map((r) => (
                          <td key={r.id} className="py-2 pr-4 text-zinc-800 dark:text-zinc-200">
                            {formatCell(field.values[String(r.id)])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="mt-2 flex items-center gap-4 text-xs text-zinc-500 dark:text-zinc-500">
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-sm bg-amber-100 dark:bg-amber-950/40" /> Partial (missing on some records)
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-sm bg-rose-100 dark:bg-rose-950/40" /> Conflict (values disagree)
                </span>
              </div>
            </section>
          </div>
        )}
      </div>

      {!loading && !error && data && (
        <div className="flex items-center justify-between border-t border-zinc-200 bg-zinc-50 px-6 py-3 dark:border-zinc-800 dark:bg-zinc-900">
          <span className="flex items-center gap-1.5 text-sm text-zinc-600 dark:text-zinc-400">
            <ShieldCheck size={15} className="text-zinc-400" />
            Match scores and rationale are computed locally. Only the AI summary above is sent to your configured
            Foundry agent, and it never writes back to this data.
          </span>
          <button
            disabled
            title="Coming in a later phase (Merge & survivorship)"
            className="flex cursor-not-allowed items-center gap-1.5 rounded-lg bg-zinc-300 px-3 py-1.5 text-sm font-medium text-zinc-500 dark:bg-zinc-700 dark:text-zinc-400"
          >
            <GitCompareArrows size={15} />
            Merge records
          </button>
        </div>
      )}
    </div>
  );
}

export default function ComparePage() {
  return (
    <Suspense fallback={<ComparePageSkeleton />}>
      <CompareContent />
    </Suspense>
  );
}
