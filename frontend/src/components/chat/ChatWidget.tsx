"use client";

import { useEffect } from "react";
import { Sparkles, X } from "lucide-react";
import { ConciergeChat } from "./ConciergeChat";
import { useConciergeChat } from "@/lib/chat";

const PANEL_WIDTH = "24rem";

// A real flex column (right section) rather than a fixed-position overlay
// drawer — toggling it open shrinks the middle section via width on this
// shrink-0 wrapper, so whatever was on screen (search results, an open
// record, the graph) stays visible next to the chat instead of getting
// covered by it. AppShell only mounts this on routes other than the home
// page ("/"), which already hosts the same conversation inline — except
// when forceOpen is set, which AppShell does on "/" itself once record
// panels take over the middle section there: the inline chat gets hidden
// along with the rest of that page's content, so the conversation has to
// relocate here (to the right) instead of disappearing.
export default function ChatWidget({ forceOpen = false }: { forceOpen?: boolean }) {
  const { panelOpen, togglePanel, closePanel, openPanel } = useConciergeChat();

  useEffect(() => {
    if (forceOpen) openPanel();
  }, [forceOpen, openPanel]);

  return (
    <>
      <div
        className="h-screen shrink-0 overflow-hidden border-l border-zinc-200 transition-[width] duration-200 dark:border-zinc-800"
        style={{ width: panelOpen ? PANEL_WIDTH : "0" }}
      >
        <div className="flex h-screen flex-col bg-white dark:bg-zinc-950" style={{ width: PANEL_WIDTH }}>
          <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-3.5 dark:border-zinc-800">
            <div className="flex items-center gap-2">
              <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-blue-600/10 text-blue-600 dark:text-blue-400">
                <Sparkles size={13} />
              </div>
              <span className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Data Concierge</span>
            </div>
            <button
              onClick={closePanel}
              aria-label="Close chat"
              className="rounded-md p-1.5 text-zinc-400 transition-colors duration-150 hover:bg-zinc-100 hover:text-zinc-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40 dark:hover:bg-zinc-800 dark:hover:text-zinc-300"
            >
              <X size={16} />
            </button>
          </div>
          <div className="min-h-0 flex-1">
            <ConciergeChat variant="drawer" />
          </div>
        </div>
      </div>

      <button
        onClick={togglePanel}
        aria-label={panelOpen ? "Close Data Concierge chat" : "Open Data Concierge chat"}
        title="Data Concierge"
        className={`fixed bottom-6 right-6 z-50 flex h-12 w-12 items-center justify-center rounded-full bg-blue-600 text-white shadow-lg transition-all duration-200 hover:bg-blue-700 hover:shadow-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50 focus-visible:ring-offset-2 ${
          panelOpen ? "scale-0 opacity-0" : "scale-100 opacity-100"
        }`}
      >
        <Sparkles size={20} />
      </button>
    </>
  );
}
