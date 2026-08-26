"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import Sidebar from "./Sidebar";
import ChatWidget from "./chat/ChatWidget";
import { useAuth } from "@/lib/auth";
import { ChatProvider } from "@/lib/chat";
import { RecordModalProvider, useRecordModal } from "@/lib/recordModal";
import { RecordPanelTray } from "./mdm/RecordPanelTray";

// The login page renders full-screen with no sidebar/app chrome; every
// other route requires a logged-in user, enforced client-side here since
// this whole app is already a client-rendered SPA-style Next.js frontend
// with no server auth of its own (see AGENTS.md — no middleware.js/
// proxy.js convention is in use).
export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading } = useAuth();
  const isLoginPage = pathname === "/login";
  const isSettingsPage = pathname.startsWith("/settings");

  useEffect(() => {
    if (!loading && !user && !isLoginPage) router.replace("/login");
  }, [loading, user, isLoginPage, router]);

  if (isLoginPage) return <>{children}</>;

  if (loading || !user) {
    return (
      <div className="flex h-screen w-full items-center justify-center text-sm text-zinc-400 dark:text-zinc-600">
        Loading…
      </div>
    );
  }

  // Settings is a standalone experience, not another module inside the
  // main shell — no main Sidebar, no floating chat widget. Matches
  // crm-poc-webapp's AppChrome, which renders /settings/* bare outside
  // the main Sidebar/ChatPanel; app/settings/layout.tsx supplies its own
  // back-to-app header + sub-nav in place of what Sidebar/ChatWidget
  // would otherwise provide.
  if (isSettingsPage) return <>{children}</>;

  return (
    <ChatProvider>
      <RecordModalProvider>
        <ShellBody isHome={pathname === "/"}>{children}</ShellBody>
      </RecordModalProvider>
    </ChatProvider>
  );
}

// Split out from AppShell because it needs useRecordModal(), which only
// works once RecordModalProvider has mounted above it.
function ShellBody({ isHome, children }: { isHome: boolean; children: React.ReactNode }) {
  const { openIds } = useRecordModal();
  const recordsOpen = openIds.length > 0;

  return (
    <>
      <Sidebar />
      <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <div className={`scrollbar-hide min-h-0 flex-1 overflow-y-auto ${recordsOpen ? "hidden" : ""}`}>
          {children}
        </div>
        <RecordPanelTray />
      </main>
      {/* The home page hosts the Concierge conversation inline as its own
          content, so the drawer is redundant there — except once open
          records take over the middle section (above), at which point the
          inline chat is hidden along with the rest of that page's content
          and has to relocate here, forced open, so it isn't lost. */}
      {(!isHome || recordsOpen) && <ChatWidget forceOpen={isHome && recordsOpen} />}
    </>
  );
}
