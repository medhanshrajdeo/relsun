"use client";

import { createContext, useContext, useMemo, useState } from "react";

const MAX_OPEN_RECORDS = 4;

type RecordPanelContextValue = {
  openIds: number[];
  open: (id: number) => void;
  close: (id: number) => void;
  closeAll: () => void;
};

const RecordPanelContext = createContext<RecordPanelContextValue | null>(null);

// Tracks which records are open as inline mini-panels in the middle
// section (see RecordPanelTray, rendered inside AppShell's <main>) rather
// than each page owning its own "which record am I viewing" state — this
// is what lets a record link inside a Concierge chat reply, Search's
// "open record" button, and Requests' "View record" link all open into
// the same shared tray. Opening more than one at once (e.g. several rows
// from Search) shows each side by side, evenly divided; past
// MAX_OPEN_RECORDS the oldest panel is evicted to make room for the new
// one rather than silently ignoring the click.
export function RecordModalProvider({ children }: { children: React.ReactNode }) {
  const [openIds, setOpenIds] = useState<number[]>([]);

  const value = useMemo<RecordPanelContextValue>(
    () => ({
      openIds,
      open: (id: number) =>
        setOpenIds((prev) => {
          if (prev.includes(id)) return prev;
          const next = [...prev, id];
          return next.length > MAX_OPEN_RECORDS ? next.slice(next.length - MAX_OPEN_RECORDS) : next;
        }),
      close: (id: number) => setOpenIds((prev) => prev.filter((existing) => existing !== id)),
      closeAll: () => setOpenIds([]),
    }),
    [openIds]
  );

  return <RecordPanelContext.Provider value={value}>{children}</RecordPanelContext.Provider>;
}

export function useRecordModal(): RecordPanelContextValue {
  const ctx = useContext(RecordPanelContext);
  if (!ctx) throw new Error("useRecordModal must be used within RecordModalProvider");
  return ctx;
}
