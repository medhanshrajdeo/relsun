import Link from "next/link";
import { ArrowRight, Sparkles } from "lucide-react";

export default function Home() {
  return (
    <div className="flex min-h-full flex-col items-center justify-center gap-6 bg-white px-6 dark:bg-zinc-950">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-600/10 text-blue-600 dark:text-blue-400">
        <Sparkles size={22} />
      </div>
      <div className="text-center">
        <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">Welcome to Data Concierge</h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          The conversational home for Relsun is coming in a later phase.
        </p>
      </div>
      <Link
        href="/mdm/search"
        className="group flex items-center gap-2 rounded-full bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
      >
        Try Master Data Search
        <ArrowRight size={15} className="transition-transform group-hover:translate-x-0.5" />
      </Link>
    </div>
  );
}
