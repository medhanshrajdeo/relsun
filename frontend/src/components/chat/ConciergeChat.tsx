"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowRight, Send, Sparkles, User } from "lucide-react";
import { useConciergeChat, type ChatMessage } from "@/lib/chat";
import { Markdown } from "@/components/mdm/Markdown";

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

function MessageBubble({ message }: { message: ChatMessage }) {
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
        className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
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

// Used both as the full-page "/" experience (variant="inline") and inside
// the floating ChatWidget's drawer (variant="drawer") on every other
// route — same context, same history, just different chrome/sizing.
export function ConciergeChat({ variant = "inline" }: { variant?: "inline" | "drawer" }) {
  const { messages, sending, send } = useConciergeChat();
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const isInline = variant === "inline";

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending]);

  const handleSend = (prompt: string) => {
    if (!prompt.trim()) return;
    send(prompt);
    setInput("");
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSend(input);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend(input);
    }
  };

  return (
    <div className={`flex h-full flex-col ${isInline ? "bg-white dark:bg-zinc-950" : ""}`}>
      {isInline && (
        <div className="border-b border-zinc-200 px-6 py-4 dark:border-zinc-800">
          <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Data Concierge</h1>
          <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">
            Ask about your master data — search, compare, or check what already exists.
          </p>
        </div>
      )}

      <div
        ref={scrollRef}
        className={`scrollbar-hide flex-1 overflow-y-auto ${isInline ? "px-6 py-5" : "px-4 py-4"}`}
      >
        {messages.length === 0 ? (
          isInline ? (
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
                    onClick={() => handleSend(s)}
                    className="rounded-full border border-zinc-200 px-4 py-2 text-sm text-zinc-600 transition-colors duration-150 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700 dark:border-zinc-800 dark:text-zinc-400 dark:hover:border-blue-900 dark:hover:bg-blue-950/30 dark:hover:text-blue-400"
                  >
                    {s}
                  </button>
                ))}
              </div>
              <Link
                href="/mdm/search"
                className="group mt-2 flex items-center gap-1.5 text-sm text-zinc-400 transition-colors duration-150 hover:text-zinc-600 dark:text-zinc-600 dark:hover:text-zinc-400"
              >
                Or browse Master Data Search directly
                <ArrowRight size={13} className="transition-transform group-hover:translate-x-0.5" />
              </Link>
            </div>
          ) : (
            <div className="flex h-full flex-col items-center justify-center gap-3 px-2 text-center">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-600/10 text-blue-600 dark:text-blue-400">
                <Sparkles size={18} />
              </div>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">
                Ask about your master data from anywhere — this conversation follows you between pages.
              </p>
            </div>
          )
        ) : (
          <div className={`flex flex-col gap-5 ${isInline ? "mx-auto max-w-3xl" : ""}`}>
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

      <form
        onSubmit={handleSubmit}
        className={`border-t border-zinc-200 dark:border-zinc-800 ${isInline ? "px-6 py-4" : "px-3 py-3"}`}
      >
        <div className={`flex items-end gap-2 ${isInline ? "mx-auto max-w-3xl" : ""}`}>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your master data…"
            rows={1}
            disabled={sending}
            className="max-h-32 flex-1 resize-none rounded-xl border border-zinc-200 bg-white px-4 py-2.5 text-sm text-zinc-900 outline-none transition-colors duration-150 placeholder:text-zinc-400 focus:border-blue-400 focus-visible:ring-2 focus-visible:ring-blue-500/30 disabled:opacity-60 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-100 dark:placeholder:text-zinc-600 dark:focus:border-blue-700"
          />
          <button
            type="submit"
            disabled={sending || !input.trim()}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-white transition-colors duration-150 hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50 disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Send"
          >
            <Send size={16} />
          </button>
        </div>
      </form>
    </div>
  );
}
