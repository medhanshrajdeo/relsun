"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Fingerprint, Waypoints, X } from "lucide-react";
import { getMasterRecord, type MasterRecordDetail } from "@/lib/api";
import { Spinner } from "@/components/Spinner";
import { DomainBadge } from "./Badges";
import { useRecordModal } from "@/lib/recordModal";

// Field ordering/labels for the common GLEIF-sourced attributes — anything
// else in `attributes` still renders below, just without a curated label.
const KNOWN_ATTRIBUTE_LABELS: Record<string, string> = {
  country: "Country",
  city: "City",
  legal_form: "Legal Form",
  status: "Status",
};

function formatAttributeLabel(key: string): string {
  return KNOWN_ATTRIBUTE_LABELS[key] ?? key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function RecordMiniPanel({ id, onClose }: { id: number; onClose: () => void }) {
  const router = useRouter();
  const [record, setRecord] = useState<MasterRecordDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setRecord(null);
    getMasterRecord(id)
      .then((data) => {
        if (!cancelled) setRecord(data);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message || "Failed to load record.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  const attributeEntries = record
    ? Object.entries(record.attributes).filter(([, value]) => value !== null && value !== undefined && value !== "")
    : [];

  return (
    <div className="flex min-w-0 flex-col overflow-hidden border-r border-zinc-200 bg-white last:border-r-0 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex items-start justify-between gap-3 border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
        <div className="min-w-0">
          {record ? (
            <>
              <h3 className="truncate text-sm font-semibold text-zinc-900 dark:text-zinc-50">{record.name}</h3>
              <div className="mt-1 flex items-center gap-2">
                <DomainBadge domain={record.domain} />
                <span className="font-mono text-xs text-zinc-400 dark:text-zinc-600">#{record.id}</span>
              </div>
            </>
          ) : (
            <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">
              {loading ? "Loading record…" : "Record"}
            </h3>
          )}
        </div>
        <button
          onClick={onClose}
          aria-label="Close"
          className="shrink-0 rounded-md p-1 text-zinc-400 transition-colors duration-150 hover:bg-zinc-100 hover:text-zinc-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40 dark:hover:bg-zinc-800 dark:hover:text-zinc-300"
        >
          <X size={15} />
        </button>
      </div>

      <div className="scrollbar-hide flex-1 overflow-y-auto px-4 py-3">
        {loading && (
          <div className="flex items-center gap-2 py-6 text-sm text-zinc-400 dark:text-zinc-600">
            <Spinner size={16} />
            Loading record…
          </div>
        )}

        {!loading && error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-400">
            {error}
          </div>
        )}

        {!loading && record && (
          <div className="space-y-3">
            {record.external_id && (
              <div className="flex items-center gap-2 text-xs text-zinc-500 dark:text-zinc-500">
                <Fingerprint size={13} />
                <span className="font-mono">{record.external_id}</span>
                <span className="text-zinc-400 dark:text-zinc-600">(LEI)</span>
              </div>
            )}

            {attributeEntries.length > 0 ? (
              <dl className="divide-y divide-zinc-100 dark:divide-zinc-800">
                {attributeEntries.map(([key, value]) => (
                  <div key={key} className="flex items-start justify-between gap-3 py-1.5 text-sm">
                    <dt className="shrink-0 text-zinc-500 dark:text-zinc-400">{formatAttributeLabel(key)}</dt>
                    <dd className="text-right text-zinc-800 dark:text-zinc-200">{String(value)}</dd>
                  </div>
                ))}
              </dl>
            ) : (
              <p className="text-sm text-zinc-400 dark:text-zinc-600">No additional attributes on file.</p>
            )}

            <p className="text-xs text-zinc-400 dark:text-zinc-600">
              Added {new Date(record.created_at).toLocaleDateString()}
            </p>
          </div>
        )}
      </div>

      {record && (
        <div className="flex justify-end border-t border-zinc-200 px-4 py-2.5 dark:border-zinc-800">
          <button
            onClick={() => {
              onClose();
              router.push(`/mdm/graph?id=${record.id}`);
            }}
            className="flex items-center gap-1.5 rounded-lg border border-zinc-200 px-2.5 py-1 text-xs font-medium text-zinc-600 transition-colors duration-150 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40 dark:border-zinc-800 dark:text-zinc-400 dark:hover:border-blue-900 dark:hover:bg-blue-950/30 dark:hover:text-blue-400"
          >
            <Waypoints size={13} />
            View relationship graph
          </button>
        </div>
      )}
    </div>
  );
}

// Takes over the whole middle section (see AppShell, which hides the
// page's own content underneath while this is showing) so opening a
// record — from a Concierge chat link, Search's "open record" button, or
// Requests' "View record" link — shows its details inline instead of a
// popup, with the full column to work with rather than a cramped strip.
// Multiple open records divide the space evenly, side by side.
export function RecordPanelTray() {
  const { openIds, close, closeAll } = useRecordModal();

  if (openIds.length === 0) return null;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center justify-between border-b border-zinc-200 bg-zinc-50 px-4 py-1.5 dark:border-zinc-800 dark:bg-zinc-900">
        <span className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-500">
          {openIds.length > 1 ? `${openIds.length} records open` : "Record"}
        </span>
        <button
          onClick={closeAll}
          className="text-xs font-medium text-zinc-400 transition-colors duration-150 hover:text-zinc-700 dark:text-zinc-500 dark:hover:text-zinc-300"
        >
          Close all
        </button>
      </div>
      <div
        className="grid min-h-0 flex-1"
        style={{ gridTemplateColumns: `repeat(${openIds.length}, minmax(0, 1fr))` }}
      >
        {openIds.map((id) => (
          <RecordMiniPanel key={id} id={id} onClose={() => close(id)} />
        ))}
      </div>
    </div>
  );
}
