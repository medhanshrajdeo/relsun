#!/usr/bin/env bash
# Rebuild deploy-combined/ from source. Run from the repo root or anywhere:
#   bash deploy-combined/build.sh
#
# What this produces: a single directory that deploys to Databricks Apps as
# ONE app running BOTH halves of Relsun (see start.sh / DEPLOY.md):
#   - Next.js standalone server (server.js + .next/ + node_modules/ + public/)
#   - FastAPI backend         (app/ + alembic/ + scripts/ + requirements.txt)
#   - app.yaml + start.sh     (the Databricks Apps entrypoint)
#
# The frontend is built with NEXT_PUBLIC_API_BASE_URL=same-origin so the
# browser calls same-origin paths (proxied to FastAPI on :8001 by
# next.config.ts). frontend/.env.production already sets this; we ALSO pass
# it inline here so the build is correct even if that file is edited. A
# stale dev value here is the exact bug DEPLOY.md documents.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FE="$REPO_ROOT/frontend"
DC="$REPO_ROOT/deploy-combined"
SA="$FE/.next/standalone"

echo ">> Building frontend (same-origin API base)…"
cd "$FE"
NEXT_PUBLIC_API_BASE_URL=same-origin NODE_ENV=production npx next build

echo ">> Assembling deploy-combined/ …"
# NOTE: do NOT touch deploy-combined/package.json. It is hand-maintained and
# deliberately minimal (runtime deps, NO "scripts" block). Databricks Apps'
# Node buildpack runs `scripts.build` if present — and the standalone
# package.json Next emits DOES carry `build: next build`, which then fails
# server-side against the pruned standalone node_modules
# ("Can't resolve 'react-dom/client'"). We ship the ALREADY-built .next and
# let start.sh run `node server.js` directly, no server-side build.
rm -rf "$DC/.next" "$DC/node_modules" "$DC/server.js" "$DC/public"
cp -r "$SA/.next"          "$DC/.next"
cp -r "$SA/node_modules"   "$DC/node_modules"
cp    "$SA/server.js"      "$DC/server.js"
# `next build --output standalone` does NOT copy these two — do it by hand.
cp -r "$FE/.next/static"   "$DC/.next/static"
cp -r "$FE/public"         "$DC/public"

if grep -q '"build"' "$DC/package.json"; then
  echo "!! FAIL: deploy-combined/package.json has a build script — Databricks will try a server-side next build and fail. Remove it." >&2
  exit 1
fi

echo ">> Verifying no dev backend URL leaked into the client bundle…"
if grep -rq "localhost:8000" "$DC/.next/static" 2>/dev/null; then
  echo "!! FAIL: localhost:8000 found in client bundle — build picked up a dev env value." >&2
  exit 1
fi
echo "   OK (BUILD_ID $(cat "$DC/.next/BUILD_ID"))"

cat <<'EOF'

Done. To deploy (the two --include flags are REQUIRED — databricks sync
honours .gitignore and would otherwise skip .next/ and node_modules/
entirely, redeploying the old bundle):

  WS=/Workspace/Users/<you>/relsun-frontend
  MSYS_NO_PATHCONV=1 databricks sync --full deploy-combined "$WS" --profile relsun \
      --include '.next/**' --include 'node_modules/**'
  MSYS_NO_PATHCONV=1 databricks apps deploy relsun-frontend --source-code-path "$WS" --profile relsun
  databricks apps get relsun-frontend --profile relsun   # wait for RUNNING, then check /health

  # sanity: workspace BUILD_ID must match local
  databricks workspace export "$WS/.next/BUILD_ID" --profile relsun
EOF
