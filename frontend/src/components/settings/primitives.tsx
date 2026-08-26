import type { ReactNode } from "react";

// Shared building blocks for every /settings/* page — one scrolling page
// per section, instant-save controls (no page-wide Save button), unbuilt
// sections rendered as a clearly-labeled StubSection rather than a dead
// link. Naming mirrors the sibling crm-poc-webapp project's settings
// primitives on purpose.

export function SettingsHeader({
  icon: Icon,
  title,
  description,
}: {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  title: string;
  description: string;
}) {
  return (
    <div className="border-b border-zinc-200 px-8 py-5 dark:border-zinc-800">
      <div className="flex items-center gap-2 text-zinc-900 dark:text-zinc-50">
        <Icon size={17} />
        <h1 className="text-base font-semibold">{title}</h1>
      </div>
      <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">{description}</p>
    </div>
  );
}

export function SettingsPage({ children }: { children: ReactNode }) {
  return <div className="mx-auto max-w-2xl px-8 py-6">{children}</div>;
}

export function SettingsSection({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <div className="border-t border-zinc-200 py-5 first:border-t-0 first:pt-0 dark:border-zinc-800">
      {title && <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">{title}</h3>}
      {children}
    </div>
  );
}

export function SettingsRow({
  label,
  description,
  children,
}: {
  label: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-6 py-2.5">
      <div>
        <p className="text-sm font-medium text-zinc-800 dark:text-zinc-200">{label}</p>
        {description && <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-500">{description}</p>}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

export function StubSection({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-center rounded-lg border border-dashed border-zinc-200 py-10 text-center dark:border-zinc-800">
      <div>
        <p className="text-sm font-medium text-zinc-500 dark:text-zinc-500">{label}</p>
        <p className="mt-1 text-xs text-zinc-400 dark:text-zinc-600">Not wired up yet — coming in a later phase.</p>
      </div>
    </div>
  );
}
