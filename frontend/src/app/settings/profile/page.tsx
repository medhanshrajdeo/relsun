"use client";

import { LogOut, User } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { SettingsHeader, SettingsPage, SettingsRow, SettingsSection } from "@/components/settings/primitives";

export default function ProfileSettingsPage() {
  const { user, logout } = useAuth();
  if (!user) return null;

  return (
    <>
      <SettingsHeader icon={User} title="Profile" description="Your account details in Relsun." />
      <SettingsPage>
        <SettingsSection title="Account">
          <SettingsRow label="Display name">
            <span className="text-sm text-zinc-700 dark:text-zinc-300">{user.display_name}</span>
          </SettingsRow>
          <SettingsRow label="Username">
            <span className="font-mono text-sm text-zinc-700 dark:text-zinc-300">{user.username}</span>
          </SettingsRow>
          <SettingsRow label="Role" description="Set by your administrator — not yet editable here.">
            <span className="text-sm text-zinc-700 dark:text-zinc-300">{user.role ?? "—"}</span>
          </SettingsRow>
        </SettingsSection>
        <SettingsSection title="Session">
          <SettingsRow label="Log out" description="End your current session on this device.">
            <button
              onClick={logout}
              className="flex items-center gap-1.5 rounded-lg border border-zinc-200 px-3 py-1.5 text-sm font-medium text-zinc-600 transition-colors duration-150 hover:border-red-300 hover:bg-red-50 hover:text-red-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500/40 dark:border-zinc-800 dark:text-zinc-400 dark:hover:border-red-900 dark:hover:bg-red-950/30 dark:hover:text-red-400"
            >
              <LogOut size={14} />
              Log out
            </button>
          </SettingsRow>
        </SettingsSection>
      </SettingsPage>
    </>
  );
}
