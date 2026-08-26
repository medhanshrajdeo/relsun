import type { Metadata } from "next";
import Script from "next/script";
import { Geist, Geist_Mono } from "next/font/google";
import AppShell from "@/components/AppShell";
import { AuthProvider } from "@/lib/auth";
import { ThemeProvider } from "@/lib/theme";
import "./globals.css";

// Applies the user's saved theme (or system preference) before hydration
// so there's no flash of the wrong theme on load. Kept in sync afterward
// by lib/theme.tsx's ThemeProvider.
const THEME_INIT_SCRIPT = `
(function () {
  try {
    var pref = localStorage.getItem("relsun:theme");
    var dark = pref === "dark" || (pref !== "light" && window.matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.classList.toggle("dark", dark);
  } catch (e) {}
})();
`;

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Relsun",
  description: "AI-native master data management",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      // The beforeInteractive theme-init script below adds/removes the
      // `dark` class before React hydrates, which will always disagree
      // with the server-rendered className — expected and harmless for
      // this one attribute, so hydration warnings for it are suppressed
      // rather than "fixed" by removing the FOUC-avoidance script.
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="h-full flex">
        <Script id="theme-init" strategy="beforeInteractive">
          {THEME_INIT_SCRIPT}
        </Script>
        <ThemeProvider>
          <AuthProvider>
            <AppShell>{children}</AppShell>
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
