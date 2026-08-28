# Deploying Relsun to Databricks Apps

Relsun ships as **one Databricks App** named `relsun-frontend` that runs
**both halves in a single container**:

| Process | Bound to | Role |
|---|---|---|
| `node server.js` | `$DATABRICKS_APP_PORT` (public) | Next.js standalone server — serves the UI, and **proxies** `/auth /search /compare /concierge /requests /graph /domains /health /master-records` to FastAPI (see `next.config.ts` rewrites) |
| `uvicorn app.main:app` | `127.0.0.1:8001` (never exposed) | FastAPI — search, compare, graph BFS, the agent hierarchy, request approve/reject |

`start.sh` launches uvicorn in the background and `exec`s `node server.js`.
Why one container and not two apps: Databricks Apps puts an OAuth SSO gate
in front of *every* request to an app, and a browser `fetch` from one app
to another can't complete that redirect. Keeping the frontend→backend hop
inside the container makes it invisible to the gate.

## Build + deploy

```bash
bash deploy-combined/build.sh          # rebuild the bundle from source

# IMPORTANT: --include '.next/**' --include 'node_modules/**'. `databricks
# sync` honours .gitignore (it walks up to the repo-root .gitignore, which
# ignores .next/ and node_modules/), so WITHOUT these two --include flags it
# silently skips the entire built frontend and you redeploy the old bundle.
# Symptom of forgetting them: the browser keeps loading the same old JS
# chunk / BUILD_ID no matter how many times you redeploy.
MSYS_NO_PATHCONV=1 databricks sync --full deploy-combined \
    /Workspace/Users/<you>/relsun-frontend --profile relsun \
    --include '.next/**' --include 'node_modules/**'

MSYS_NO_PATHCONV=1 databricks apps deploy relsun-frontend \
    --source-code-path /Workspace/Users/<you>/relsun-frontend --profile relsun
databricks apps get relsun-frontend --profile relsun     # wait for RUNNING
```

To confirm the workspace actually has the new build before deploying:
`databricks workspace export /Workspace/Users/<you>/relsun-frontend/.next/BUILD_ID`
must match `cat deploy-combined/.next/BUILD_ID`. If a previous sync left
stale files, `databricks workspace delete .../.next --recursive` first.

Then verify in a browser (workspace SSO logs you straight in):
`https://relsun-frontend-7474659130414957.aws.databricksapps.com` — log in
as `alice`/`alice123`, run a search, open a graph, send a Concierge message.

`build.sh` is the single source of truth for assembling this directory. Do
not hand-edit `server.js`, `.next/`, `node_modules/`, or `public/` here —
they are build output and will be overwritten. Do edit `app/`, `alembic/`,
`scripts/`, `requirements.txt`, `app.yaml`, `start.sh`.

**`deploy-combined/package.json` is special: keep it minimal, no `scripts`
block.** Databricks Apps' Node buildpack runs `scripts.build` if it finds
one. We ship an *already-built* `.next` and run `node server.js` directly
via `start.sh`, so a server-side build must not happen. The standalone
`package.json` that `next build` emits *does* carry `"build": "next
build"`; if that lands here, the platform runs `next build` on the pruned
standalone `node_modules` and it dies with
`Module not found: Can't resolve 'react-dom/client'`. `build.sh` leaves
this file alone and asserts it has no `"build"` key. The correct contents:
name `relsun-combined-deploy`, `private: true`, and a flat `dependencies`
list (`next`, `react`, `react-dom`, `d3-force`, `lucide-react`,
`react-markdown`, `remark-gfm`) — nothing else.

Note: `databricks apps get` shows a `deployment` history; a build takes
~6 min (it downloads PyTorch/CUDA for `sentence-transformers`).

### Idle auto-stop

On the current tier the App's compute stops after inactivity, and when it
does the active deployment is cleared — the app needs a **redeploy**, not
just a restart. `databricks apps start relsun-frontend --profile relsun`
does both. If the browser shows an error after the app has sat unused,
this is almost always why.

## The `NEXT_PUBLIC_API_BASE_URL` bug (fixed 2026-08-27)

**Symptom:** every API call from the deployed UI failed. In the browser
Network tab: `POST http://localhost:8000/auth/login` → 503. The login page
showed "Failed to fetch".

**Cause:** `NEXT_PUBLIC_*` env vars are inlined into the JS bundle **at
build time**, not read at runtime. The `deploy-combined/.next` bundle had
been built on a machine where `frontend/.env.local` set
`NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` (the correct *local dev*
value). That literal got baked into the deployed bundle, so every
visitor's browser tried to call **their own** `localhost:8000` instead of
a same-origin path. Setting the var in `app.yaml` does **not** fix it —
runtime env can't change an already-inlined literal.

**Fix (three layers, so it can't regress):**

1. **`frontend/.env.production`** (committed) sets
   `NEXT_PUBLIC_API_BASE_URL=same-origin`. `next build` loads this
   automatically, so any production build is correct by default.
   `frontend/.env.development` (committed) keeps `http://localhost:8000`
   for `next dev`. The old uncommitted `frontend/.env.local`, which
   overrode *both*, was removed.
2. **`deploy-combined/build.sh`** also passes
   `NEXT_PUBLIC_API_BASE_URL=same-origin` inline on the build command
   (shell env beats every `.env*` file) and then greps the output bundle
   for `localhost:8000`, failing the build if it's present.
3. **`frontend/src/lib/api.ts`** has a runtime fallback: if no build-time
   value is present and the page is running in a browser on a
   non-`localhost` host, it uses same-origin (`""`) regardless. So even a
   mis-built bundle won't point a real visitor at localhost.

To confirm a build is clean:
`grep -r localhost:8000 deploy-combined/.next/static` must return nothing.
