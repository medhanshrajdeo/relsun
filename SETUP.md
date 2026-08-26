# Relsun — Setup Guide

Getting a second machine running Relsun from scratch. This is **not**
a `git clone` and go — the app runs against a real ~3.4M-row dataset
that isn't (and shouldn't be) checked into git, so there's a real data
ingestion step involved. Budget 30–60 minutes, most of it unattended
download/processing time (plus however long Databricks trial/workspace
signup takes the first time — see step 0).

If you get stuck, `CLAUDE.md` and `RELSUN_HANDBOOK.md` in the repo root
have the full architecture/product context this guide doesn't repeat.

> **Platform note (2026-08-24, corrected 2026-08-25):** Relsun runs on
> **Databricks Lakebase** (a managed, Postgres-wire-compatible OLTP
> database) — the live trial workspace is on **AWS**, not Azure — not a
> local Docker Postgres + Neo4j pair. See `CLAUDE.md`'s Platform pivot
> section for why. There is no `docker-compose.yml` anymore; the app
> connects straight to your Lakebase instance, including in local dev.
> Also note: Lakebase's connect UI defaults to **OAuth-only** — native
> Postgres password auth throws a real security warning if you enable it
> ("exposes it to the open internet") — so step 2 below provisions a
> Databricks service principal instead of a plain role/password.

---

## 0. Prerequisites

- **Git**, with access to the private repo (ask to be added as a
  collaborator on `github.com/medhanshrajdeo/relsun` if you can't clone it)
- **A Databricks workspace** (AWS-hosted, via Databricks' AWS Quickstart —
  needs an AWS account to sign into, but no manual S3/VPC/IAM setup: this
  trial's Quickstart path uses Databricks-managed serverless storage) with
  a **Lakebase database project** and a **service principal** added to
  the workspace (see step 2 below if you don't have these yet)
- **Python 3.11+** (built and verified on 3.13)
- **Node.js 20+** and npm
- An **Anthropic API key** (console.anthropic.com) — needed for the AI
  agents (Concierge chat, Compare summaries, Party requests). Search,
  Compare, and View Graph all work without one; anything conversational
  will return a clean "not configured" error until you add it.

---

## 1. Clone and configure environment

```bash
git clone https://github.com/medhanshrajdeo/relsun.git
cd relsun
cp .env.example .env
```

Edit `.env` and fill in:

```
ANTHROPIC_API_KEY=sk-ant-...          # your own key, never share/commit this
ANTHROPIC_MODEL=claude-haiku-4-5-20251001   # or claude-sonnet-5 — either works, haiku is cheaper for dev
```

`DATABASE_URL` gets filled in during step 2, once your Lakebase instance
exists.

**Never commit `.env` or paste your API key anywhere outside this file**
— it's already gitignored, keep it that way.

---

## 2. Provision Databricks Lakebase

**2a. Create the Lakebase project.** In your Databricks workspace, go to
**Compute → Lakebase** → **Go to Lakebase Postgres** → **Create project**
(name it e.g. `relsun-db`, Postgres 17, same region as your workspace).
Wait for its compute to go **Active**.

**2b. Create a service principal for the app.** Lakebase's connect UI
defaults to OAuth-only, and enabling native password auth throws a real
Databricks warning about exposing the database to the open internet — so
the app authenticates as a Databricks identity, not a plain
username/password:

1. Account console → **User management → Service principals → Add
   service principal**. Name it e.g. `relsun-backend`.
2. On that service principal's **Credentials & secrets** tab, under
   **OAuth secrets**, click **Generate secret** — scope **Other APIs →
   `all-apis`** (Lakebase has no narrower scope yet), any lifetime.
   **Copy the secret immediately — it's shown once.** Also note the
   service principal's **Application ID** from the account console's
   Service principals list.
3. Add it to your workspace (not just the account): workspace **Settings
   → Identity and access → Service principals → Add service principal**
   → select it. **Don't grant it admin** — it only needs database access,
   granted in the next step.
4. Back in the Lakebase project: **Branches → production → Roles &
   Databases → Add role** → Authentication type **OAuth** → search for
   the service principal by name and select it → leave **System roles**
   unchecked (no `databricks_superuser`) → **Add**. This creates a
   Postgres role named after its Application ID.
5. In the Lakebase project's **SQL Editor**, grant it what it needs:
   ```sql
   GRANT ALL PRIVILEGES ON DATABASE databricks_postgres TO "<application-id>";
   GRANT ALL ON SCHEMA public TO "<application-id>";
   CREATE EXTENSION IF NOT EXISTS vector;
   CREATE EXTENSION IF NOT EXISTS pg_trgm;
   ```
   Both extensions are required — `vector` backs semantic search
   (`MasterRecord.embedding`), `pg_trgm` backs fuzzy/typo-tolerant search
   (`app/search.py`). If either `CREATE EXTENSION` fails, stop here and
   check the Lakebase docs for your workspace/region before continuing.

**2c. Set `.env`.** From the project dashboard's **Connect** dialog, copy
the host (the part after `@` in the shown connection string, e.g.
`ep-xxxxx.database.us-east-1.cloud.databricks.com`) and your workspace URL
(the browser's host, e.g. `https://dbc-xxxxx.cloud.databricks.com`):

```
DATABASE_URL=postgresql+psycopg://<application-id>@<lakebase-host>:5432/databricks_postgres?sslmode=require
DATABRICKS_HOST=<your-workspace-url>
DATABRICKS_CLIENT_ID=<application-id>
DATABRICKS_CLIENT_SECRET=<the OAuth secret from 2b, copied once>
```

Note `DATABASE_URL` has **no password** — the real credential is a
short-lived OAuth token, minted per-connection from the
`DATABRICKS_CLIENT_ID`/`DATABRICKS_CLIENT_SECRET` pair by
`app/lakebase_auth.py` (see `CLAUDE.md`'s Platform pivot section for the
full mechanics). Never commit the client secret any more than you would
a plain password.

---

## 3. Backend setup

```bash
cd backend
python -m venv .venv

# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

pip install -r requirements.txt
alembic upgrade head
python -m scripts.seed_users
```

`alembic upgrade head` creates all tables (`master_records`,
`word_frequencies`, `master_data_requests`, `audit_log`, `users`,
`user_sessions`, `relationship_edges`) against the empty Lakebase
instance from step 2.
`scripts.seed_users` creates the two demo logins used to exercise the
multi-user Master Data Request flow — `alice` / `alice123` (Sales Rep)
and `bob` / `bob123` (Data Steward). The whole app requires being logged
in as one of these; there's no self-service signup.

**Sanity check** — start the API without any data loaded yet:

```bash
uvicorn app.main:app --reload --port 8000
```

Visit `http://localhost:8000/health` — should return
`{"status":"ok","database":"connected"}`. Stop it (Ctrl+C) before moving
to the next step; you'll restart it once real data is loaded.

> **If `uvicorn` never binds to the port and there's no visible error:**
> `sentence_transformers`' import chain pulls in `transformers`, which
> tries to load a TensorFlow/Keras backend and can crash the whole app at
> module-import time before uvicorn ever opens its socket
> (`ValueError: ... Keras 3 ... not yet supported in Transformers`) — this
> repo has no TensorFlow usage anywhere, `transformers` is just probing
> for a backend that happens to be broken in some environments. Fix: set
> `USE_TF=0` before starting uvicorn (every invocation in this doc), e.g.
> `USE_TF=0 uvicorn app.main:app --reload --port 8000` (bash) or
> `$env:USE_TF=0; uvicorn app.main:app --reload --port 8000` (PowerShell).

---

## 4. Load the real dataset (GLEIF)

This is the step that actually takes time. Relsun's master data comes
from **GLEIF's public Legal Entity Identifier registry** — real
companies, real ownership data, no synthetic/invented records (see
`DATA_STRATEGY.md` for why that matters here).

### 4a. Download the bulk files

From GLEIF's Golden Copy download page —
**https://www.gleif.org/en/lei-data/gleif-golden-copy/download-the-golden-copy**
— download the two **Concatenated File** XML downloads:

- **Level 1** (LEI-CDF v3.1) — entity records — save as
  `backend/data/gleif/level1.zip`
- **Level 2** (RR-CDF v2.1) — relationship records — save as
  `backend/data/gleif/level2.zip`

Create the `backend/data/gleif/` folder if it doesn't exist. Combined
these are roughly 500MB zipped; Level 1 alone is ~8.3GB uncompressed, so
the ingestion scripts below stream-parse rather than loading either file
fully into memory — expect them to take real minutes, not seconds. This
folder is gitignored on purpose — never try to commit these files.

### 4b. Run the ingestion pipeline, in this exact order

All commands run from `backend/` with the venv active:

```bash
python -m scripts.ingest_gleif_entities        # Lakebase: ~3.4M Party records
python -m scripts.flag_demo_customers           # tags 3 real entities as "existing customer" demo data
python -m scripts.ingest_gleif_relationships    # Lakebase: ~250K real ownership edges (relationship_edges table) — GLEIF's Level 2 file grows over time, so this count drifts upward on a fresh pull
python -m scripts.refresh_word_frequencies      # Lakebase: search relevance-ranking stats
```

Each script logs progress as it goes and is safe to re-run if
interrupted (each truncates/MERGEs idempotently — see the docstring at
the top of each file for specifics).

> **Do not run `scripts/seed.py`, `scripts/seed_data.py`, or
> `scripts/seed_graph.py`.** These are leftover from an early
> hand-picked demo dataset that was fully superseded by the real GLEIF
> load above — `seed.py` will `DELETE` every real record already loaded
> and replace it with ~17 fake ones. They're still in the repo for
> history but are not part of the current setup.

---

## 5. Frontend setup

In a separate terminal:

```bash
cd frontend
npm install
```

---

## 6. Run it

Two terminals, both from the repo root:

**Backend:**
```bash
cd backend
.venv\Scripts\activate    # or source .venv/bin/activate on Mac/Linux
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm run dev
```

Open **http://localhost:3000**. You'll land on the sign-in screen — log
in as `alice` / `alice123` or `bob` / `bob123` (both printed on the
login page itself). You should then land on the Data Concierge chat
screen with "Backend connected" showing in the bottom-left corner.

---

## 7. Verify it's actually working

- **Search** (`/mdm/search`): search "Hanger" — should return several
  real GLEIF-loaded companies as Exact matches, including "Hanger, Inc."
- **Compare**: select two Search results, compare them — deterministic
  field diffs should appear instantly; the AI summary panel above it
  will show either a drafted narrative or a clean "not configured"
  message, depending on whether step 1's API key is set
- **View Graph**: search "Boeing", open "THE BOEING COMPANY" (flagged as
  an `existing_customer` by `flag_demo_customers.py`), View Graph — should
  render its real GLEIF-reported subsidiaries (e.g. Boeing Capital
  Corporation, Boeing India). Record IDs aren't stable across a fresh
  ingest, so look it up by name rather than a hardcoded `?id=`. If this is
  empty, `ingest_gleif_relationships.py` didn't complete successfully
- **Data Concierge** (`/`): ask "Does Hanger Inc already exist in our
  system?" — needs a real `ANTHROPIC_API_KEY`; returns a clean
  "not available" message otherwise, not an error
- **Master Data Requests** (`/mdm/requests`): should load an empty
  Review Queue with no errors
- **Multi-user request flow**: log in as `alice`, submit a create
  request via chat (e.g. "Create a new Party record named Test Corp in
  country USA"), then use the logout icon at the bottom of the sidebar
  and log back in as `bob` — the Review Queue should show the request
  Alice submitted, with "Requested by: Alice"; approving it as Bob
  should show "Decided by: Bob"
- **Record link in chat**: ask the Concierge to search for an entity
  that exists (e.g. "Search for Hanger") — matching records should
  render as clickable links; clicking one opens that record's detail in
  a modal without navigating away from the chat

---

## Troubleshooting

- **`alembic upgrade head` (or anything else) fails with `fe_sendauth: no
  password supplied`** — something is connecting without going through
  `app.db.engine`'s OAuth token hook. If you wrote a new script that talks
  to Postgres directly instead of importing `engine` from `app.db`, use
  `app.lakebase_auth.get_raw_dsn()` for its DSN instead of building one
  from `settings.database_url` yourself (see `ingest_gleif_entities.py`
  for the pattern) — `DATABASE_URL` deliberately has no password (step 2c).
- **`alembic upgrade head` fails to connect for another reason** —
  double-check `DATABASE_URL`/`DATABRICKS_*` in `.env` against step 2c,
  and confirm the Lakebase project's compute shows **Active**.
- **`alembic upgrade head` fails on `CREATE EXTENSION` / a
  `Vector`/`TSVECTOR` column** — go back to step 2b: `vector` and
  `pg_trgm` must be created on the Lakebase database before the first
  migration runs; they're not enabled by default.
- **`ingest_gleif_entities.py` fails with `cannot truncate a table
  referenced in a foreign key constraint`** — expected if
  `relationship_edges` already has rows from a prior run; the script's
  `TRUNCATE ... CASCADE` handles this, so this only surfaces if you've
  edited that statement.
- **Search/Compare pages load but show no results ever** — the GLEIF
  ingestion (step 4) either didn't run or didn't finish; re-run
  `ingest_gleif_entities.py`, it's safe to re-run (truncates and
  reloads).
- **Everything conversational (Concierge chat, AI summaries) returns
  "not configured" (HTTP 503)** — `ANTHROPIC_API_KEY` is missing or
  empty in `.env`; restart the backend after adding it.
- **`ANTHROPIC_MODEL` errors with a 404 from Anthropic** — the model ID
  string is wrong (this has happened once already — `claude-haiku-4.5`
  is invalid, the real ID is `claude-haiku-4-5-20251001`). Check
  console.anthropic.com for current valid model IDs if unsure.
