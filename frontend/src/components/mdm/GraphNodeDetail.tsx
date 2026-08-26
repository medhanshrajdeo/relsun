"use client";

import { Fingerprint, Sparkles, Waypoints, X } from "lucide-react";
import type { GraphNode } from "@/lib/api";
import { DomainBadge } from "./Badges";
import { useRecordModal } from "@/lib/recordModal";

interface Props {
  node: GraphNode;
  degree: number;
  onClose: () => void;
  onRecenter: () => void;
}

// Styled to match RecordPanelTray's mini-panel (header / dl-based body /
// footer actions) so a user sees the same visual language whether they
// opened a record from Search, a Concierge chat link, or here.
export function GraphNodeDetail({ node, degree, onClose, onRecenter }: Props) {
  const { open } = useRecordModal();

  return (
    <div className="flex w-72 shrink-0 flex-col overflow-hidden border-l border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex items-start justify-between gap-3 border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-zinc-900 dark:text-zinc-50">{node.name ?? "Unknown"}</h3>
          <div className="mt-1 flex items-center gap-2">
            {node.domain && <DomainBadge domain={node.domain} />}
            <span className="font-mono text-xs text-zinc-400 dark:text-zinc-600">#{node.id}</span>
          </div>
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
        <div className="space-y-3">
          {node.existing_customer && (
            <div className="flex items-center gap-1.5 rounded-lg bg-amber-50 px-2.5 py-1.5 text-xs font-medium text-amber-800 dark:bg-amber-950/30 dark:text-amber-300">
              <Sparkles size={13} />
              Existing Customer
            </div>
          )}

          {node.lei && (
            <div className="flex items-center gap-2 text-xs text-zinc-500 dark:text-zinc-500">
              <Fingerprint size={13} />
              <span className="font-mono">{node.lei}</span>
              <span className="text-zinc-400 dark:text-zinc-600">(LEI)</span>
            </div>
          )}

          <dl className="divide-y divide-zinc-100 dark:divide-zinc-800">
            <div className="flex items-center justify-between gap-3 py-1.5 text-sm">
              <dt className="text-zinc-500 dark:text-zinc-400">Connections in this view</dt>
              <dd className="font-medium text-zinc-800 dark:text-zinc-200">{degree}</dd>
            </div>
            {node.is_anchor && (
              <div className="flex items-center justify-between gap-3 py-1.5 text-sm">
                <dt className="text-zinc-500 dark:text-zinc-400">Role</dt>
                <dd className="text-zinc-800 dark:text-zinc-200">Anchor (centered)</dd>
              </div>
            )}
          </dl>
        </div>
      </div>

      <div className="flex items-center justify-end gap-2 border-t border-zinc-200 px-4 py-2.5 dark:border-zinc-800">
        {!node.is_anchor && (
          <button
            onClick={onRecenter}
            className="flex items-center gap-1.5 rounded-lg border border-zinc-200 px-2.5 py-1 text-xs font-medium text-zinc-600 transition-colors duration-150 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40 dark:border-zinc-800 dark:text-zinc-400 dark:hover:border-blue-900 dark:hover:bg-blue-950/30 dark:hover:text-blue-400"
          >
            <Waypoints size={13} />
            Recenter graph here
          </button>
        )}
        <button
          onClick={() => open(node.id)}
          className="flex items-center gap-1.5 rounded-lg bg-zinc-900 px-2.5 py-1 text-xs font-medium text-white transition-colors duration-150 hover:bg-zinc-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          Open record
        </button>
      </div>
    </div>
  );
}
