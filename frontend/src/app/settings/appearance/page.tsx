"use client";

import { Check, Monitor, Moon, Palette, Sun } from "lucide-react";
import { useTheme, type ThemePreference } from "@/lib/theme";
import { SettingsHeader, SettingsPage, SettingsSection } from "@/components/settings/primitives";

const OPTIONS: { value: ThemePreference; label: string; icon: React.ComponentType<{ size?: number }> }[] = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
];

export default function AppearanceSettingsPage() {
  const { theme, setTheme } = useTheme();

  return (
    <>
      <SettingsHeader icon={Palette} title="Appearance" description="Choose how Relsun looks on this device." />
      <SettingsPage>
        <SettingsSection title="Theme">
          <div className="grid grid-cols-3 gap-3">
            {OPTIONS.map(({ value, label, icon: Icon }) => {
              const active = theme === value;
              return (
                <button
                  key={value}
                  onClick={() => setTheme(value)}
                  aria-pressed={active}
                  className={`relative flex flex-col items-center gap-2 rounded-xl border px-4 py-4 text-sm font-medium transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40 ${
                    active
                      ? "border-blue-500 bg-blue-50 text-blue-700 dark:border-blue-600 dark:bg-blue-950/30 dark:text-blue-400"
                      : "border-zinc-200 text-zinc-600 hover:border-zinc-300 hover:bg-zinc-50 dark:border-zinc-800 dark:text-zinc-400 dark:hover:border-zinc-700 dark:hover:bg-zinc-900"
                  }`}
                >
                  {active && <Check size={13} className="absolute right-2 top-2 text-blue-600 dark:text-blue-400" />}
                  <Icon size={18} />
                  {label}
                </button>
              );
            })}
          </div>
        </SettingsSection>
      </SettingsPage>
    </>
  );
}
