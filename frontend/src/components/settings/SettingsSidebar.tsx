"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bell, Palette, User } from "lucide-react";

const SETTINGS_NAV = [
  { label: "Profile", href: "/settings/profile", icon: User },
  { label: "Appearance", href: "/settings/appearance", icon: Palette },
  { label: "Notifications", href: "/settings/notifications", icon: Bell },
];

export default function SettingsSidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-full w-56 shrink-0 flex-col border-r border-zinc-200 bg-zinc-50/50 px-3 py-5 dark:border-zinc-800 dark:bg-zinc-950/50">
      <h2 className="px-2 pb-3 text-xs font-semibold uppercase tracking-wide text-zinc-400 dark:text-zinc-600">
        Settings
      </h2>
      <nav className="space-y-0.5">
        {SETTINGS_NAV.map(({ label, href, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-2 rounded-md px-2 py-1.5 text-sm font-medium transition-colors duration-150 ${
                active
                  ? "bg-blue-600/10 text-blue-700 dark:text-blue-400"
                  : "text-zinc-600 hover:bg-zinc-200/60 dark:text-zinc-400 dark:hover:bg-zinc-800/60"
              }`}
            >
              <Icon size={15} className="shrink-0" />
              {label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
