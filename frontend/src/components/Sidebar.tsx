"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BookOpen,
  ChevronDown,
  ChevronRight,
  CircleCheckBig,
  Database,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { API_BASE_URL } from "@/lib/api";

type NavLeaf = { label: string; href?: string };
type NavSection = { label: string; href?: string; icon: React.ComponentType<{ size?: number; className?: string }>; children?: NavLeaf[] };

const NAV: NavSection[] = [
  { label: "Data Concierge", href: "/", icon: Sparkles },
  {
    label: "Data Catalog",
    icon: BookOpen,
    children: [
      { label: "Data Dictionary" },
      { label: "Data Ontology" },
      { label: "Data Lineage" },
      { label: "Change Requests" },
    ],
  },
  {
    label: "Data Governance",
    icon: ShieldCheck,
    children: [
      { label: "Data Policies" },
      { label: "Data Standards" },
      { label: "Change Requests" },
      { label: "Issue Management" },
    ],
  },
  {
    label: "Data Quality",
    icon: CircleCheckBig,
    children: [
      { label: "Data Quality Checks" },
      { label: "Change Requests" },
      { label: "Issue Management" },
    ],
  },
  {
    label: "Master Data Management",
    icon: Database,
    children: [
      { label: "Master Data Search", href: "/mdm/search" },
      { label: "Master Data Requests" },
    ],
  },
];

function ComingSoonPill() {
  return (
    <span className="ml-auto rounded-full bg-zinc-200 px-1.5 py-0.5 text-[10px] font-medium text-zinc-500 dark:bg-zinc-800 dark:text-zinc-500">
      Soon
    </span>
  );
}

function ConnectionStatus() {
  const [connected, setConnected] = useState<boolean | null>(null);

  useEffect(() => {
    const check = () =>
      fetch(`${API_BASE_URL}/health`)
        .then((res) => res.json())
        .then((data) => setConnected(data.status === "ok"))
        .catch(() => setConnected(false));
    check();
    const interval = setInterval(check, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex items-center gap-2 px-3 py-2.5 text-xs text-zinc-500 dark:text-zinc-500">
      <span className="relative flex h-1.5 w-1.5 shrink-0">
        {connected && (
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500/60" />
        )}
        <span
          className={`relative inline-flex h-1.5 w-1.5 rounded-full ${
            connected === null ? "bg-zinc-400" : connected ? "bg-emerald-500" : "bg-red-500"
          }`}
        />
      </span>
      <span>{connected === null ? "Connecting..." : connected ? "Backend connected" : "Backend unreachable"}</span>
    </div>
  );
}

export default function Sidebar() {
  const pathname = usePathname();
  const [openSections, setOpenSections] = useState<Set<string>>(
    () => new Set(["Master Data Management"])
  );

  const toggleSection = (label: string) => {
    setOpenSections((prev) => {
      const next = new Set(prev);
      if (next.has(label)) next.delete(label);
      else next.add(label);
      return next;
    });
  };

  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col border-r border-zinc-200 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex items-center gap-2 px-4 py-4">
        <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-blue-600 text-xs font-bold text-white">
          R
        </div>
        <span className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Relsun</span>
      </div>

      <nav className="flex-1 space-y-0.5 overflow-y-auto px-2">
        {NAV.map((section) => {
          const Icon = section.icon;

          if (!section.children) {
            const active = pathname === section.href;
            return (
              <Link
                key={section.label}
                href={section.href ?? "#"}
                className={`flex items-center gap-2 rounded-md px-2 py-1.5 text-sm font-medium ${
                  active
                    ? "bg-blue-600/10 text-blue-700 dark:text-blue-400"
                    : "text-zinc-700 hover:bg-zinc-200/60 dark:text-zinc-300 dark:hover:bg-zinc-800/60"
                }`}
              >
                <Icon size={16} className="shrink-0" />
                {section.label}
              </Link>
            );
          }

          const isOpen = openSections.has(section.label);
          const hasActiveChild = section.children.some((c) => c.href && pathname === c.href);

          return (
            <div key={section.label}>
              <button
                onClick={() => toggleSection(section.label)}
                className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm font-medium ${
                  hasActiveChild
                    ? "text-blue-700 dark:text-blue-400"
                    : "text-zinc-700 dark:text-zinc-300"
                } hover:bg-zinc-200/60 dark:hover:bg-zinc-800/60`}
              >
                <Icon size={16} className="shrink-0" />
                <span className="flex-1">{section.label}</span>
                {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              </button>
              {isOpen && (
                <div className="ml-2 space-y-0.5 border-l border-zinc-200 pl-4 dark:border-zinc-800">
                  {section.children.map((item) => {
                    const active = item.href && pathname === item.href;
                    if (!item.href) {
                      return (
                        <span
                          key={item.label}
                          title="Coming in a later phase"
                          className="flex cursor-not-allowed items-center rounded-md px-2 py-1.5 text-sm text-zinc-400 dark:text-zinc-600"
                        >
                          {item.label}
                          <ComingSoonPill />
                        </span>
                      );
                    }
                    return (
                      <Link
                        key={item.label}
                        href={item.href}
                        className={`block rounded-md px-2 py-1.5 text-sm ${
                          active
                            ? "bg-blue-600/10 text-blue-700 dark:text-blue-400"
                            : "text-zinc-600 hover:bg-zinc-200/60 dark:text-zinc-400 dark:hover:bg-zinc-800/60"
                        }`}
                      >
                        {item.label}
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </nav>

      <div className="border-t border-zinc-200 dark:border-zinc-800">
        <span
          title="Coming in a later phase"
          className="flex cursor-not-allowed items-center px-4 py-3 text-sm text-zinc-400 dark:text-zinc-600"
        >
          My Account
          <ComingSoonPill />
        </span>
        <ConnectionStatus />
      </div>
    </aside>
  );
}
