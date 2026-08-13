"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowRight, Send, Sparkles, User } from "lucide-react";
import { ConciergeUnavailableError, sendConciergeChat, type ConciergeChatTurn } from "@/lib/api";
import { Markdown } from "@/components/mdm/Markdown";

type Message = ConciergeChatTurn & { error?: boolean };

const SUGGESTIONS = [
  "Does Hanger Inc already exist in our system?",
  "Search for a company called Boeng",
  "Compare Hanger Inc and Hanger Solution",
];

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 px-1 py-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-1.5 w-1.5 animate-bounce rounded-full bg-zinc-400 dark:bg-zinc-600"
          style={{ animationDelay: `${i * 120}ms` }}
        />
      ))}
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex items-start gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      <div
        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${
          isUser
            ? "bg-zinc-200 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"
            : "bg-blue-600/10 text-blue-600 dark:text-blue-400"
        }`}
      >
        {isUser ? <User size={14} /> : <Sparkles size={14} />}
      </div>
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
          isUser
            ? "bg-blue-600 text-white whitespace-pre-wrap"
            : message.error
              ? "border border-red-200 bg-red-50 text-red-700 whitespace-pre-wrap dark:border-red-900 dark:bg-red-950/40 dark:text-red-400"
              : "border border-zinc-200 bg-zinc-50 text-zinc-800 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-200"
        }`}
      >
        {isUser || message.error ? message.content : <Markdown text={message.content} />}
      </div>
    </div>
  );
}

function HomeContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const autoSentRef = useRef(false);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending]);

  // A UI-action-generated prompt (e.g. "Create as new Party record" on a
  // no-results Search) — one click sends a predefined prompt straight into
  // the same Concierge path a typed message would take, per the pivot
  // addendum's trigger types. Strip it from the URL right away so
  // reloading/back doesn't resend it. autoSentRef guards against React
  // Strict Mode's dev-only double-invoke of effects on mount — without it
  // this fired the prompt twice, submitting two separate requests.
  useEffect(() => {
    const prefilled = searchParams.get("prompt");
    if (prefilled && !autoSentRef.current) {
      autoSentRef.current = true;
      router.replace("/", { scroll: false });
      send(prefilled);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
    setInput("");
    setSending(true);

    sendConciergeChat(trimmed, historyForRequest)
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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    send(input);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  };

  return (
    <div className="flex h-full flex-col bg-white dark:bg-zinc-950">
      <div className="border-b border-zinc-200 px-6 py-4 dark:border-zinc-800">
        <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Data Concierge</h1>
        <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">
          Ask about your master data — search, compare, or check what already exists.
        </p>
      </div>

      <div ref={scrollRef} className="scrollbar-hide flex-1 overflow-y-auto px-6 py-5">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-6 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-600/10 text-blue-600 dark:text-blue-400">
              <Sparkles size={22} />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">
                How can we help you today?
              </h2>
              <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
                Try one of these, or ask your own question.
              </p>
            </div>
            <div className="flex flex-col gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded-full border border-zinc-200 px-4 py-2 text-sm text-zinc-600 transition-colors hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700 dark:border-zinc-800 dark:text-zinc-400 dark:hover:border-blue-900 dark:hover:bg-blue-950/30 dark:hover:text-blue-400"
                >
                  {s}
                </button>
              ))}
            </div>
            <Link
              href="/mdm/search"
              className="group mt-2 flex items-center gap-1.5 text-sm text-zinc-400 transition-colors hover:text-zinc-600 dark:text-zinc-600 dark:hover:text-zinc-400"
            >
              Or browse Master Data Search directly
              <ArrowRight size={13} className="transition-transform group-hover:translate-x-0.5" />
            </Link>
          </div>
        ) : (
          <div className="mx-auto flex max-w-3xl flex-col gap-5">
            {messages.map((m, i) => (
              <MessageBubble key={i} message={m} />
            ))}
            {sending && (
              <div className="flex items-start gap-3">
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue-600/10 text-blue-600 dark:text-blue-400">
                  <Sparkles size={14} />
                </div>
                <div className="rounded-2xl border border-zinc-200 bg-zinc-50 px-4 py-2.5 dark:border-zinc-800 dark:bg-zinc-900">
                  <TypingIndicator />
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit} className="border-t border-zinc-200 px-6 py-4 dark:border-zinc-800">
        <div className="mx-auto flex max-w-3xl items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your master data…"
            rows={1}
            disabled={sending}
            className="max-h-32 flex-1 resize-none rounded-xl border border-zinc-200 bg-white px-4 py-2.5 text-sm text-zinc-900 outline-none placeholder:text-zinc-400 focus:border-blue-400 disabled:opacity-60 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-100 dark:placeholder:text-zinc-600 dark:focus:border-blue-700"
          />
          <button
            type="submit"
            disabled={sending || !input.trim()}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Send"
          >
            <Send size={16} />
          </button>
        </div>
      </form>
    </div>
  );
}

export default function Home() {
  return (
    <Suspense fallback={<div className="h-full bg-white dark:bg-zinc-950" />}>
      <HomeContent />
    </Suspense>
  );
}
