"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, ArrowRight, Maximize2, Minimize2, Sparkles, ZoomIn } from "lucide-react";
import { fetchRelationshipGraph, type GraphResponse } from "@/lib/api";
import { RelationshipGraph } from "@/components/mdm/RelationshipGraph";
import { DomainBadge } from "@/components/mdm/Badges";

const HOP_OPTIONS = [1, 2, 3] as const;

function GraphPageSkeleton() {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-zinc-200 px-6 py-4 dark:border-zinc-800">
        <div className="h-5 w-48 animate-pulse rounded bg-zinc-200 dark:bg-zinc-800" />
      </div>
      <div className="flex-1 px-6 py-4">
        <div className="h-full animate-pulse rounded-lg bg-zinc-100 dark:bg-zinc-900" />
      </div>
    </div>
  );
}

function GraphContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const idParam = searchParams.get("id");
  const id = idParam ? Number(idParam) : null;
  const hops = Number(searchParams.get("hops") ?? "2");

  const [data, setData] = useState<GraphResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (!expanded) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setExpanded(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [expanded]);

  useEffect(() => {
    if (id === null || !Number.isFinite(id)) {
      setError("No record selected. Open a graph from a search result.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    fetchRelationshipGraph(id, hops)
      .then((res) => {
        setData(res);
        setLoading(false);
      })
      .catch((err: Error) => {
        setError(err.message || "Failed to load graph. Is the backend running?");
        setLoading(false);
      });
  }, [id, hops]);

  const recenter = (newId: number) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("id", String(newId));
    router.push(`/mdm/graph?${params.toString()}`);
  };

  const setHops = (h: number) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("hops", String(h));
    router.push(`/mdm/graph?${params.toString()}`);
  };

  const anchor = data?.nodes.find((n) => n.is_anchor);
  const otherCustomers = data?.nodes.filter((n) => n.existing_customer && !n.is_anchor) ?? [];

  return (
    <div className={expanded ? "fixed inset-0 z-50 flex flex-col bg-white dark:bg-zinc-950" : "flex h-full flex-col"}>
      <div className="flex items-center justify-between gap-3 border-b border-zinc-200 px-6 py-4 dark:border-zinc-800">
        <div className="flex items-center gap-3">
          {!expanded && (
            <button
              onClick={() => router.back()}
              className="flex items-center gap-1.5 rounded-md p-1.5 text-zinc-500 hover:bg-zinc-100 hover:text-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-300"
              aria-label="Back to search"
            >
              <ArrowLeft size={16} />
            </button>
          )}
          <div>
            <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
              {anchor ? anchor.name : "Relationship Graph"}
            </h1>
            <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">
              {data ? `${data.nodes.length} entities, ${data.edges.length} relationships` : "Loading…"}
              {data?.truncated ? " · view truncated, zoom in with fewer hops for full detail" : ""}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="mr-1 flex items-center gap-1 text-xs font-medium text-zinc-500 dark:text-zinc-400">
            <ZoomIn size={13} /> Hops:
          </span>
          {HOP_OPTIONS.map((h) => (
            <button
              key={h}
              onClick={() => setHops(h)}
              className={`rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
                hops === h
                  ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                  : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-700"
              }`}
            >
              {h}
            </button>
          ))}
          <button
            onClick={() => setExpanded((v) => !v)}
            title={expanded ? "Exit fullscreen (Esc)" : "Expand to fullscreen"}
            className="ml-2 flex items-center gap-1.5 rounded-md p-1.5 text-zinc-500 hover:bg-zinc-100 hover:text-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-300"
          >
            {expanded ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-hidden px-6 py-4">
        {loading && <GraphPageSkeleton />}

        {!loading && error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-400">
            {error}{" "}
            <Link href="/mdm/search" className="font-medium underline">
              Back to search
            </Link>
          </div>
        )}

        {!loading && !error && data && data.nodes.length === 1 && (
          <div className="flex h-full flex-col items-center justify-center text-center text-zinc-400 dark:text-zinc-600">
            <p className="text-sm">No known relationships for this record yet.</p>
            <p className="mt-1 text-xs">Try increasing hops, or check back once more relationship data is loaded.</p>
          </div>
        )}

        {!loading && !error && data && data.nodes.length > 1 && (
          <div className="h-full">
            <RelationshipGraph key={`${data.center_id}-${hops}`} data={data} onNodeClick={recenter} />
          </div>
        )}
      </div>

      {!loading && !error && otherCustomers.length > 0 && (
        <div className="flex items-center justify-between border-t border-amber-200 bg-amber-50 px-6 py-3 dark:border-amber-900 dark:bg-amber-950/30">
          <span className="flex items-center gap-1.5 text-sm text-amber-800 dark:text-amber-300">
            <Sparkles size={15} />
            {otherCustomers.length === 1
              ? `${otherCustomers[0].name} in this chain is an existing customer.`
              : `${otherCustomers.length} entities in this chain are existing customers.`}{" "}
            This relationship could accelerate a deal.
          </span>
          <button
            disabled
            title="Coming in a later phase (Master Data Requests) — will open a request to act on this relationship"
            className="flex cursor-not-allowed items-center gap-1.5 rounded-lg bg-amber-300 px-3 py-1.5 text-sm font-medium text-amber-900 dark:bg-amber-800 dark:text-amber-200"
          >
            Act on this relationship
          </button>
        </div>
      )}

      {!loading && !error && data && data.nodes.length > 1 && (
        <div className="flex items-center gap-4 border-t border-zinc-200 px-6 py-2.5 text-xs text-zinc-500 dark:border-zinc-800 dark:text-zinc-500">
          <span>
            Drag nodes to rearrange · scroll to zoom · click a node to recenter · arrows point owner{" "}
            <ArrowRight size={11} className="inline -translate-y-px" /> subsidiary
          </span>
          {anchor && (
            <span className="ml-auto flex items-center gap-1.5">
              Centered on <DomainBadge domain={anchor.domain ?? "Unknown"} /> {anchor.name}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

export default function GraphPage() {
  return (
    <Suspense fallback={<GraphPageSkeleton />}>
      <GraphContent />
    </Suspense>
  );
}
