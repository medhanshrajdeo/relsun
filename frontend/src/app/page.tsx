"use client";

import { useEffect, useState } from "react";

type HealthResponse = {
  status: string;
  database: string;
  detail?: string;
};

export default function Home() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
    fetch(`${apiBaseUrl}/health`)
      .then((res) => res.json())
      .then(setHealth)
      .catch((err) => setError(err.message));
  }, []);

  const connected = health?.status === "ok";

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-zinc-50 dark:bg-black">
      <h1 className="text-2xl font-semibold text-black dark:text-zinc-50">Relsun</h1>
      <div className="flex items-center gap-2 text-sm">
        <span
          className={`h-2 w-2 rounded-full ${
            connected ? "bg-emerald-500" : health ? "bg-red-500" : "bg-zinc-400"
          }`}
        />
        <span className="text-zinc-600 dark:text-zinc-400">
          {error
            ? `Backend unreachable: ${error}`
            : health
              ? `API: ${health.status} · Database: ${health.database}`
              : "Checking backend..."}
        </span>
      </div>
    </div>
  );
}
