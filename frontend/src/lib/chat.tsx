"use client";

import { createContext, useContext, useEffect, useRef, useState } from "react";
import { ConciergeUnavailableError, sendConciergeChat, type ConciergeChatTurn, type GraphResponse } from "./api";
import { useAuth } from "./auth";

export type ChatMessage = ConciergeChatTurn & { error?: boolean };

const HISTORY_STORAGE_PREFIX = "relsun:chat-history";

type ChatContextValue = {
  messages: ChatMessage[];
  sending: boolean;
  send: (prompt: string) => void;
  panelOpen: boolean;
  togglePanel: () => void;
  closePanel: () => void;
  openPanel: () => void;
  // The relationship graph currently on screen, if any — the graph page
  // publishes its already-fetched data here so a chat message sent while
  // it's open rides along as context (see graph_context_agent.py on the
  // backend). Any other page leaves this null.
  setGraphContext: (ctx: GraphResponse | null) => void;
};

const ChatContext = createContext<ChatContextValue | null>(null);

// Mounted once above routed content (in AppShell) rather than inside any
// one page, so the conversation survives client-side navigation between
// modules for free. sessionStorage (keyed per user, cleared on logout)
// additionally survives a hard refresh within the same browser tab.
// panelOpen also lives here rather than inside ChatWidget itself so
// AppShell can size the middle section around it — the drawer is a real
// flex column that pushes the rest of the layout over, not an overlay
// that hides whatever's underneath it.
export function ChatProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sending, setSending] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const loadedForUserId = useRef<number | null>(null);
  // Read only at send() time — not rendered anywhere in this provider —
  // but plain state (not a ref) so the graph page's effect that sets it
  // follows normal React data flow.
  const [graphContext, setGraphContext] = useState<GraphResponse | null>(null);

  useEffect(() => {
    if (!user) {
      setMessages([]);
      loadedForUserId.current = null;
      return;
    }
    if (loadedForUserId.current === user.id) return;
    loadedForUserId.current = user.id;
    try {
      const stored = sessionStorage.getItem(`${HISTORY_STORAGE_PREFIX}:${user.id}`);
      setMessages(stored ? JSON.parse(stored) : []);
    } catch {
      setMessages([]);
    }
  }, [user]);

  useEffect(() => {
    if (!user) return;
    try {
      sessionStorage.setItem(`${HISTORY_STORAGE_PREFIX}:${user.id}`, JSON.stringify(messages));
    } catch {
      // Private browsing / quota-exceeded — chat still works in-memory for this tab.
    }
  }, [messages, user]);

  const send = (prompt: string) => {
    const trimmed = prompt.trim();
    if (!trimmed || sending) return;

    // History sent to the backend excludes the just-added user turn (the
    // endpoint takes prior history + the new prompt separately) and any
    // error turns — those never happened as far as the agent is concerned.
    const historyForRequest: ConciergeChatTurn[] = messages
      .filter((m) => !m.error)
      .map(({ role, content }) => ({ role, content }));

    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setSending(true);

    sendConciergeChat(trimmed, historyForRequest, graphContext)
      .then((response) => {
        setMessages((prev) => [...prev, { role: "assistant", content: response }]);
      })
      .catch((err: Error) => {
        const message =
          err instanceof ConciergeUnavailableError
            ? "The Data Concierge isn't available yet — no Anthropic API key is configured in this environment."
            : err.message || "Something went wrong reaching the Concierge. Is the backend running?";
        setMessages((prev) => [...prev, { role: "assistant", content: message, error: true }]);
      })
      .finally(() => setSending(false));
  };

  const togglePanel = () => setPanelOpen((prev) => !prev);
  const closePanel = () => setPanelOpen(false);
  const openPanel = () => setPanelOpen(true);

  return (
    <ChatContext.Provider
      value={{ messages, sending, send, panelOpen, togglePanel, closePanel, openPanel, setGraphContext }}
    >
      {children}
    </ChatContext.Provider>
  );
}

export function useConciergeChat(): ChatContextValue {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useConciergeChat must be used within ChatProvider");
  return ctx;
}
