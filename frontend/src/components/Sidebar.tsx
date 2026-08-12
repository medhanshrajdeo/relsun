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
  PanelLeftClose,
  PanelLeftOpen,
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

const COLLAPSE_STORAGE_KEY = "relsun:sidebar-collapsed";

function ComingSoonPill() {
  return (
    <span className="ml-auto rounded-full bg-zinc-200 px-1.5 py-0.5 text-[10px] font-medium text-zinc-500 dark:bg-zinc-800 dark:text-zinc-500">
      Soon
    </span>
  );
}

function ConnectionStatus({ collapsed }: { collapsed: boolean }) {
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

  const dot = (
    <span className="relative flex h-1.5 w-1.5 shrink-0">
      {connected && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500/60" />}
      <span
        className={`relative inline-flex h-1.5 w-1.5 rounded-full ${
          connected === null ? "bg-zinc-400" : connected ? "bg-emerald-500" : "bg-red-500"
        }`}
      />
    </span>
  );

  if (collapsed) {
    return (
      <div
        className="flex justify-center py-2.5"
        title={connected === null ? "Connecting..." : connected ? "Backend connected" : "Backend unreachable"}
      >
        {dot}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 px-3 py-2.5 text-xs text-zinc-500 dark:text-zinc-500">
      {dot}
      <span>{connected === null ? "Connecting..." : connected ? "Backend connected" : "Backend unreachable"}</span>
    </div>
  );
}

export default function Sidebar() {
  const pathname = usePathname();
  const [openSections, setOpenSections] = useState<Set<string>>(
    () => new Set(["Master Data Management"])
  );
  const [collapsed, setCollapsed] = useState(false);

  // Read persisted collapse state after mount only — localStorage isn't
  // available during SSR, and reading it in the initial useState would
  // desync from the server-rendered markup and trigger a hydration warning.
  useEffect(() => {
    const stored = localStorage.getItem(COLLAPSE_STORAGE_KEY);
    if (stored) setCollapsed(stored === "true");
  }, []);

  const toggleCollapsed = () => {
    setCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem(COLLAPSE_STORAGE_KEY, String(next));
      return next;
    });
  };

  const toggleSection = (label: string) => {
    setOpenSections((prev) => {
      const next = new Set(prev);
      if (next.has(label)) next.delete(label);
      else next.add(label);
      return next;
    });
  };

  return (
    <aside
      className={`flex h-screen shrink-0 flex-col border-r border-zinc-200 bg-zinc-50 transition-[width] duration-150 dark:border-zinc-800 dark:bg-zinc-950 ${
        collapsed ? "w-14" : "w-64"
      }`}
    >
      <div className={`flex items-center gap-2 px-4 py-4 ${collapsed ? "flex-col px-2" : ""}`}>
        <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-blue-600 text-xs font-bold text-white">
          R
        </div>
        {!collapsed && <span className="flex-1 text-sm font-semibold text-zinc-900 dark:text-zinc-50">Relsun</span>}
        <button
          onClick={toggleCollapsed}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="rounded-md p-1 text-zinc-400 hover:bg-zinc-200/60 hover:text-zinc-700 dark:text-zinc-500 dark:hover:bg-zinc-800/60 dark:hover:text-zinc-300"
        >
          {collapsed ? <PanelLeftOpen size={15} /> : <PanelLeftClose size={15} />}
        </button>
      </div>

      <nav className={`scrollbar-hide flex-1 space-y-0.5 overflow-y-auto px-2 ${collapsed ? "px-1.5" : ""}`}>
        {NAV.map((section) => {
          const Icon = section.icon;

          if (!section.children) {
            const active = pathname === section.href;
            return (
              <Link
                key={section.label}
                href={section.href ?? "#"}
                title={collapsed ? section.label : undefined}
                className={`flex items-center gap-2 rounded-md px-2 py-1.5 text-sm font-medium ${collapsed ? "justify-center" : ""} ${
                  active
                    ? "bg-blue-600/10 text-blue-700 dark:text-blue-400"
                    : "text-zinc-700 hover:bg-zinc-200/60 dark:text-zinc-300 dark:hover:bg-zinc-800/60"
                }`}
              >
                <Icon size={16} className="shrink-0" />
                {!collapsed && section.label}
              </Link>
            );
          }

          const isOpen = openSections.has(section.label);
          const hasActiveChild = section.children.some((c) => c.href && pathname === c.href);

          if (collapsed) {
            return (
              <div
                key={section.label}
                title={section.label}
                className={`flex items-center justify-center rounded-md px-2 py-1.5 ${
                  hasActiveChild ? "text-blue-700 dark:text-blue-400" : "text-zinc-700 dark:text-zinc-300"
                } hover:bg-zinc-200/60 dark:hover:bg-zinc-800/60`}
              >
                <Icon size={16} className="shrink-0" />
              </div>
            );
          }

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
        {collapsed ? (
          <div className="flex justify-center py-3 text-zinc-400 dark:text-zinc-600" title="My Account — coming in a later phase">
            <span className="text-xs">···</span>
          </div>
        ) : (
          <span
            title="Coming in a later phase"
            className="flex cursor-not-allowed items-center px-4 py-3 text-sm text-zinc-400 dark:text-zinc-600"
          >
            My Account
            <ComingSoonPill />
          </span>
        )}
        <ConnectionStatus collapsed={collapsed} />
      </div>
    </aside>
  );
}
