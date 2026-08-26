import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import SettingsSidebar from "@/components/settings/SettingsSidebar";

// Standalone page — deliberately outside the main app shell (see
// AppShell.tsx). No main Sidebar or floating chat widget here, so this
// header is what replaces them: brand mark + a way back to the app.
export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen w-full flex-col bg-white dark:bg-zinc-950">
      <div className="flex items-center gap-3 border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
        <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-blue-600 text-xs font-bold text-white">
          R
        </div>
        <Link
          href="/"
          className="flex items-center gap-1.5 rounded-md px-2 py-1 text-sm font-medium text-zinc-600 transition-colors duration-150 hover:bg-zinc-100 hover:text-zinc-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
        >
          <ArrowLeft size={15} />
          Back to Relsun
        </Link>
      </div>
      <div className="flex flex-1 overflow-hidden">
        <SettingsSidebar />
        <div className="scrollbar-hide flex-1 overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}
