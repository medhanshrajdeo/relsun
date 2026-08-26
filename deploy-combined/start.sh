#!/bin/sh
# Runs both halves of Relsun in one Databricks App: FastAPI stays bound to
# localhost only (never exposed by Databricks' routing) and Next.js's own
# server proxies to it internally via next.config.ts rewrites. That hop
# never leaves the container, so it's invisible to Databricks' per-app SSO
# gate — the thing that broke calling a *separate* backend app from the
# browser (every request, not just page loads, got redirected to OAuth).
set -e

uvicorn app.main:app --host 127.0.0.1 --port 8001 &

exec node server.js
