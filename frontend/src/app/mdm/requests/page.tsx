"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, Clock, RefreshCw, X } from "lucide-react";
import {
  approveRequest,
  listRequests,
  rejectRequest,
  type MasterDataRequest,
  type MasterDataRequestStatus,
} from "@/lib/api";
import { DomainBadge } from "@/components/mdm/Badges";
import { useRecordModal } from "@/lib/recordModal";

const STATUS_FILTERS: { label: string; value: MasterDataRequestStatus | "all" }[] = [
  { label: "Pending", value: "pending" },
  { label: "All", value: "all" },
];

const TYPE_LABEL: Record<MasterDataRequest["request_type"], string> = {
  create: "Create",
  update: "Update",
  delete: "Delete",
};

const STATUS_STYLES: Record<MasterDataRequestStatus, string> = {
  pending: "border border-amber-400 text-amber-700 dark:border-amber-500 dark:text-amber-400",
  approved: "bg-emerald-600 text-white",
  published: "bg-emerald-600 text-white",
  rejected: "border border-zinc-300 text-zinc-500 dark:border-zinc-700 dark:text-zinc-500",
};

function StatusBadge({ status }: { status: MasterDataRequestStatus }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${STATUS_STYLES[status]}`}>
      {status}
    </span>
  );
}

// Every request type describes itself differently — a create has no
// target yet, update/delete have no name of their own to show.
function describeChange(request: MasterDataRequest): string {
  if (request.request_type === "create") {
    const name = (request.proposed_attributes?.name as string | undefined) ?? "(no name given)";
    return `New Party: ${name}`;
  }
  if (request.request_type === "delete") {
    return `Delete record #${request.target_record_id}`;
  }
  const fields = request.proposed_attributes ? Object.keys(request.proposed_attributes).join(", ") : "";
  return `Update record #${request.target_record_id}${fields ? ` — ${fields}` : ""}`;
}

export default function RequestsPage() {
  const { open: openRecord } = useRecordModal();
  const [filter, setFilter] = useState<MasterDataRequestStatus | "all">("pending");
  const [requests, setRequests] = useState<MasterDataRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actingOn, setActingOn] = useState<number | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    listRequests(filter === "all" ? undefined : filter)
      .then(setRequests)
      .catch((err: Error) => setError(err.message || "Failed to load requests. Is the backend running?"))
      .finally(() => setLoading(false));
  }, [filter]);

  useEffect(() => {
    load();
  }, [load]);

  const handleDecision = async (id: number, action: "approve" | "reject") => {
    setActingOn(id);
    setError(null);
    try {
      await (action === "approve" ? approveRequest(id) : rejectRequest(id));
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${action}.`);
    } finally {
      setActingOn(null);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-zinc-200 px-6 py-4 dark:border-zinc-800">
        <div>
          <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Master Data Requests</h1>
          <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">
            Review proposed changes before they reach master data.
          </p>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-1.5 rounded-md p-2 text-zinc-500 transition-colors duration-150 hover:bg-zinc-100 hover:text-zinc-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40 dark:hover:bg-zinc-800 dark:hover:text-zinc-300"
          aria-label="Refresh"
        >
          <RefreshCw size={15} />
        </button>
      </div>

      <div className="flex items-center gap-2 border-b border-zinc-200 px-6 py-3 dark:border-zinc-800">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40 ${
              filter === f.value
                ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-700"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="scrollbar-hide flex-1 overflow-y-auto px-6 py-5">
        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-400">
            {error}
          </div>
        )}

        {loading && <div className="h-24 animate-pulse rounded-lg bg-zinc-100 dark:bg-zinc-900" />}

        {!loading && requests.length === 0 && !error && (
          <div className="flex h-full flex-col items-center justify-center gap-2 py-16 text-center text-zinc-400 dark:text-zinc-600">
            <Clock size={28} />
            <p className="text-sm">No {filter === "all" ? "" : filter} requests.</p>
          </div>
        )}

        {!loading && requests.length > 0 && (
          <div className="overflow-hidden rounded-lg border border-zinc-200 dark:border-zinc-800">
            <table className="w-full min-w-max border-collapse text-sm">
              <thead>
                <tr className="border-b border-zinc-200 bg-zinc-50 text-left dark:border-zinc-800 dark:bg-zinc-900">
                  <th className="py-2.5 pl-4 pr-4 text-xs font-medium uppercase tracking-wide text-zinc-500">
                    Domain
                  </th>
                  <th className="py-2.5 pr-4 text-xs font-medium uppercase tracking-wide text-zinc-500">Type</th>
                  <th className="py-2.5 pr-4 text-xs font-medium uppercase tracking-wide text-zinc-500">Change</th>
                  <th className="py-2.5 pr-4 text-xs font-medium uppercase tracking-wide text-zinc-500">Status</th>
                  <th className="py-2.5 pr-4 text-xs font-medium uppercase tracking-wide text-zinc-500">
                    Requested by
                  </th>
                  <th className="py-2.5 pr-4 text-xs font-medium uppercase tracking-wide text-zinc-500">
                    Decided by
                  </th>
                  <th className="py-2.5 pr-4 text-xs font-medium uppercase tracking-wide text-zinc-500">
                    Submitted
                  </th>
                  <th className="py-2.5 pr-4 text-xs font-medium uppercase tracking-wide text-zinc-500">Actions</th>
                </tr>
              </thead>
              <tbody>
                {requests.map((r) => (
                  <tr key={r.id} className="border-b border-zinc-100 last:border-0 dark:border-zinc-900">
                    <td className="py-2.5 pl-4 pr-4">
                      <DomainBadge domain={r.domain} />
                    </td>
                    <td className="py-2.5 pr-4 text-zinc-700 dark:text-zinc-300">{TYPE_LABEL[r.request_type]}</td>
                    <td className="py-2.5 pr-4 text-zinc-800 dark:text-zinc-200">
                      {describeChange(r)}
                      {r.target_record_id && (
                        <button
                          onClick={() => openRecord(r.target_record_id as number)}
                          className="ml-2 rounded text-xs font-medium text-blue-600 underline transition-colors duration-150 hover:text-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40 dark:text-blue-400 dark:hover:text-blue-300"
                        >
                          View record
                        </button>
                      )}
                    </td>
                    <td className="py-2.5 pr-4">
                      <StatusBadge status={r.status} />
                    </td>
                    <td className="py-2.5 pr-4 text-zinc-600 dark:text-zinc-400">
                      {r.submitted_by?.display_name ?? <span className="text-zinc-400 dark:text-zinc-600">—</span>}
                    </td>
                    <td className="py-2.5 pr-4 text-zinc-600 dark:text-zinc-400">
                      {r.decided_by?.display_name ?? <span className="text-zinc-400 dark:text-zinc-600">—</span>}
                    </td>
                    <td className="py-2.5 pr-4 text-xs text-zinc-500 dark:text-zinc-500">
                      {new Date(r.submitted_at).toLocaleString()}
                    </td>
                    <td className="py-2.5 pr-4">
                      {r.status === "pending" ? (
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => handleDecision(r.id, "approve")}
                            disabled={actingOn === r.id}
                            className="flex items-center gap-1 rounded-md bg-emerald-600 px-2.5 py-1 text-xs font-medium text-white transition-colors duration-150 hover:bg-emerald-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            <Check size={12} /> Approve
                          </button>
                          <button
                            onClick={() => handleDecision(r.id, "reject")}
                            disabled={actingOn === r.id}
                            className="flex items-center gap-1 rounded-md border border-zinc-300 px-2.5 py-1 text-xs font-medium text-zinc-600 transition-colors duration-150 hover:bg-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40 disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800"
                          >
                            <X size={12} /> Reject
                          </button>
                        </div>
                      ) : (
                        <span className="text-xs text-zinc-400 dark:text-zinc-600">{r.decision_note || "—"}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
