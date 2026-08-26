import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Deployed to Databricks Apps as a standalone Node server, not `next start`
  // — see the standalone-folder prep in the deploy step.
  output: "standalone",

  // Databricks Apps gates *every* request to an app behind its own SSO —
  // including plain API calls, not just page loads — with no way to turn
  // it off. Two separate Databricks Apps (frontend + backend) calling each
  // other over the public internet can never cleanly share that session:
  // a cross-origin fetch from the browser has no way to complete Databricks'
  // OAuth redirect, so it just fails. The fix is to run FastAPI as a second
  // process inside this same app (see start.sh) bound to localhost only,
  // and have Next.js's own server proxy these paths to it here — that hop
  // never leaves the container, so it's invisible to Databricks' per-app
  // SSO gate entirely. NEXT_PUBLIC_API_BASE_URL is set to "" for this
  // deployment so the browser calls these same-origin paths directly.
  async rewrites() {
    return [
      { source: "/health", destination: "http://localhost:8001/health" },
      { source: "/auth/:path*", destination: "http://localhost:8001/auth/:path*" },
      { source: "/domains", destination: "http://localhost:8001/domains" },
      { source: "/search", destination: "http://localhost:8001/search" },
      { source: "/master-records/:path*", destination: "http://localhost:8001/master-records/:path*" },
      { source: "/compare", destination: "http://localhost:8001/compare" },
      { source: "/compare/:path*", destination: "http://localhost:8001/compare/:path*" },
      { source: "/concierge/:path*", destination: "http://localhost:8001/concierge/:path*" },
      { source: "/requests", destination: "http://localhost:8001/requests" },
      { source: "/requests/:path*", destination: "http://localhost:8001/requests/:path*" },
      { source: "/graph/:path*", destination: "http://localhost:8001/graph/:path*" },
    ];
  },
};

export default nextConfig;
