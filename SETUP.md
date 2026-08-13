# Relsun — Setup Guide

Getting a second machine running Relsun from scratch. This is **not**
a `git clone` and go — the app runs against a real ~3.4M-row dataset
that isn't (and shouldn't be) checked into git, so there's a real data
ingestion step involved. Budget 30–60 minutes, most of it unattended
download/processing time.

If you get stuck, `CLAUDE.md` and `RELSUN_HANDBOOK.md` in the repo root
have the full architecture/product context this guide doesn't repeat.

---

## 0. Prerequisites

- **Git**, with access to the private repo (ask to be added as a
  collaborator on `github.com/medhanshrajdeo/relsun` if you can't clone it)
- **Docker Desktop**, running
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

Everything else in `.env.example` (Postgres/Neo4j credentials, ports) is
already set to sane local-dev defaults — no need to change those unless
something else on your machine is already using those ports.

**Never commit `.env` or paste your API key anywhere outside this file**
— it's already gitignored, keep it that way.

---

## 2. Start the databases

```bash
docker compose up -d
```

This starts Postgres (with pgvector + pg_trgm) on port `5433` and Neo4j
on ports `7474`/`7687`. Give it ~10–15 seconds, then confirm both are
healthy:

```bash
docker ps
```

You should see both `relsun-postgres-1` and `relsun-neo4j-1` listed as
`healthy`.

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
```

`alembic upgrade head` creates all tables (`master_records`,
`word_frequencies`, `master_data_requests`, `audit_log`) against the
empty Postgres instance from step 2.

**Sanity check** — start the API without any data loaded yet:

```bash
uvicorn app.main:app --reload --port 8000
```

Visit `http://localhost:8000/health` — should return
`{"status":"ok","database":"connected"}`. Stop it (Ctrl+C) before moving
to the next step; you'll restart it once real data is loaded.

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
python -m scripts.ingest_gleif_entities        # Postgres: ~3.4M Party records
python -m scripts.flag_demo_customers           # tags 3 real entities as "existing customer" demo data
python -m scripts.load_gleif_graph_nodes        # Neo4j: pushes every record in as a graph node
python -m scripts.ingest_gleif_relationships    # Neo4j: ~169K real ownership edges
python -m scripts.refresh_word_frequencies      # Postgres: search relevance-ranking stats
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

Open **http://localhost:3000**. You should land on the Data Concierge
chat screen with "Backend connected" showing in the bottom-left corner.

---

## 7. Verify it's actually working

- **Search** (`/mdm/search`): search "Hanger" — should return several
  real GLEIF-loaded companies as Exact matches, including "Hanger, Inc."
- **Compare**: select two Search results, compare them — deterministic
  field diffs should appear instantly; the AI summary panel above it
  will show either a drafted narrative or a clean "not configured"
  message, depending on whether step 1's API key is set
- **View Graph** (`/mdm/graph?id=1842436`): should render a force-directed
  graph with ~40 nodes (Standard Bank Group Limited and its real
  subsidiaries) — if this is empty, `load_gleif_graph_nodes.py` and/or
  `ingest_gleif_relationships.py` didn't complete successfully
- **Data Concierge** (`/`): ask "Does Hanger Inc already exist in our
  system?" — needs a real `ANTHROPIC_API_KEY`; returns a clean
  "not available" message otherwise, not an error
- **Master Data Requests** (`/mdm/requests`): should load an empty
  Review Queue with no errors

---

## Troubleshooting

- **`docker ps` shows containers unhealthy / restarting** — check
  `docker compose logs postgres` / `docker compose logs neo4j`. Most
  common cause on a fresh machine: another Postgres/Neo4j already
  running locally on the same ports — either stop it or change the
  ports in `.env`.
- **`alembic upgrade head` fails to connect** — confirm `docker ps`
  shows Postgres as `healthy` first; it needs a few seconds after
  `docker compose up -d` before it's ready.
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
