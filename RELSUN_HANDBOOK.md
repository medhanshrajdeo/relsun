# Relsun — Complete Product & Technical Handbook

> **Snapshot document.** This captures Relsun exactly as it exists as of
> **2026-08-26** (refreshed from the prior 2026-08-13 snapshot — the
> intervening two weeks moved a lot: real auth, a full platform migration
> off Docker Postgres/Neo4j onto Databricks Lakebase, a Recommendation
> Agent, and a Graph Context sub-agent). Unlike `CLAUDE.md` (the living
> day-to-day reference, updated continuously as work happens), this file
> is **not** auto-maintained — per direct instruction, it only changes
> when explicitly asked to update it again. If you're reading this later
> and something looks off, check `CLAUDE.md` and the actual code before
> trusting this over them.
>
> Written for someone seeing Relsun for the first time. Every example
> below is a real, actually-executed input/output from this build — not
> invented illustrations.

---

## 1. What Relsun Is

Relsun is an **AI-native Master Data Management (MDM) platform**. The
differentiator over a conventional MDM system of record: discovering a
relationship in the data — e.g. a sales prospect turns out to be owned by
a parent company that's also an existing customer — is meant to actually
**trigger a workflow** (a Master Data Request, an approval chain), not
just render a pretty visualization. "The graph drives action, not just
insight."

The founders' original wireframe deck lays out five product areas:

| Area                       | Status                                           |
| -------------------------- | ------------------------------------------------ |
| **Data Concierge**         | ✅ Built — AI chat interface, home screen        |
| **Data Catalog**           | ⬜ Not built — sidebar placeholder only          |
| **Data Governance**        | ⬜ Not built — sidebar placeholder only          |
| **Data Quality**           | ⬜ Not built — sidebar placeholder only          |
| **Master Data Management** | ✅ Built — Search, Compare, View Graph, Requests |
| **My Account**             | ⬜ Not built — sidebar placeholder only          |

Everything documented in this handbook lives under **Data Concierge** and
**Master Data Management** — the other three modules exist in the
sidebar nav (matching the wireframe) with a "Soon" badge and no code
behind them at all.

---

## 2. Architecture Pivot (why the system looks the way it does)

Two architectural decisions, made 2026-08-12, shape everything below:

1. **No visual workflow builder.** An earlier plan called for a
   drag-and-drop Trigger → Logic → Action → AI canvas (Attio-style) forloo
   configuring automation. Rejected: agentic systems shouldn't be
   authored as a rigid step-1-then-step-2 sequence. Replaced with a
   **hierarchy of agents that call each other as tools** — each agent's
   own plain-English instructions decide, at runtime, which sub-agent (if
   any) a given prompt should route to. Nothing is hardcoded as a fixed
   chain.
2. **Foundry is a UX reference only, not the runtime.** Microsoft
   Foundry's agent portal — specifically its "an agent's tools can
   include other agents" pattern — is what the hierarchy below is
   modeled on. But the actual runtime is **plain Python calling the
   Anthropic API directly** (the `anthropic` SDK), no Azure dependency at
   all.

Full history of this decision: `CONFIGURABLE_WORKFLOWS_AGENTS.md`'s
"Agent Architecture Pivot" addendum. Full planned agent inventory across
all four modules (most unbuilt): `AGENT_INVENTORY.md`.

---

## 3. Tech Stack

- **Backend:** Python, FastAPI, SQLAlchemy 2.0, **Databricks Lakebase**
  (managed Postgres-wire-compatible OLTP under Unity Catalog, `relsun-db`
  project, Postgres 17, `us-east-1`) with pgvector + pg_trgm, Alembic
  migrations. Replaces both the original Docker Postgres instance *and*
  standalone Neo4j — see the Platform Pivot in §3a below. `docker-compose.yml`
  and `db/init/` are gone; local dev connects straight to Lakebase.
- **Auth:** real session-based login (`backend/app/auth.py`) — stdlib
  PBKDF2-HMAC-SHA256 password hashing (no bcrypt/passlib dependency; this
  is a handful of internal demo users, not a public signup surface),
  opaque server-side session tokens in a `user_sessions` table (not a
  JWT, so `POST /auth/logout` can actually revoke a session rather than
  the client merely discarding a self-contained token). See §8a.
- **Frontend:** Next.js (App Router), TypeScript, Tailwind CSS,
  lucide-react icons, d3-force (physics only — rendering is hand-written
  React SVG), react-markdown + remark-gfm (chat/summary rendering)
- **Embeddings:** sentence-transformers `all-MiniLM-L6-v2`, local, lazy
  (generated only for records actually touched by a search/compare —
  never pre-computed for the full bulk-loaded set)
- **AI agents:** `anthropic` Python SDK, called directly — no agent
  framework/SDK dependency beyond the `Agent`/`Tool` classes built in
  this repo (`backend/app/agents/framework.py`). Model is set via
  `ANTHROPIC_MODEL` in `.env` (local dev currently runs
  `claude-haiku-4-5-20251001` for cost-efficient verification;
  `config.py`'s fallback default is `claude-sonnet-5` — either is valid,
  it's a per-environment choice)
- **Testing:** pytest, real Postgres (Lakebase) wrapped in a rolled-back
  SAVEPOINT per test (`backend/tests/conftest.py`) — zero cost, nothing
  persists, no mocking of the database layer. 22 tests passing as of this
  snapshot.

### 3a. Platform Pivot (2026-08-24/25): Databricks Lakebase, not Docker Postgres + Neo4j

Executed and fully verified end-to-end, not just planned. What moved: the
data layer only — the agent architecture is untouched (Foundry was
already "UX reference only, not a runtime dependency," see §2, and stays
that way).

- **Why Databricks:** the user signed up for a Databricks trial and chose
  it as Relsun's target data platform, superseding an earlier
  Microsoft-Fabric-leaning default that was never actually built against.
- **Why AWS, not Azure:** an explicit cost/maturity comparison — Lakebase
  itself is identical software regardless of cloud, and AWS won on cost
  and on the original "move away from Microsoft" motivation. The
  workspace uses Databricks-managed serverless storage (AWS Quickstart) —
  no customer-owned S3/VPC/IAM stack to manage.
- **Neo4j → `relationship_edges` table.** The relationship graph
  (previously Neo4j Cypher, `-[*1..N]-` undirected multi-hop) is now a
  plain Postgres table in the same Lakebase instance, walked via an
  iterative BFS in `app/graph.py` (§7) instead of Cypher — chosen over a
  single recursive CTE because it's simpler to bound safely: `limit` caps
  the number of *nodes* admitted per hop, which is what actually protects
  against a high-fan-out hub entity (a real company can have 50+ direct
  subsidiaries).
- **Data reload:** all ~3.4M GLEIF entities, the demo `existing_customer`
  flags, and ~257K ownership edges were reloaded from the same source
  ZIPs (no re-download needed) — a real number update from the original
  ~169K edge count in §4/§7, not a typo.
- **Auth to Lakebase itself:** a static Postgres password was the
  original plan, but the moment the real instance was provisioned,
  enabling native password auth threw a real Databricks warning ("exposes
  it to the open internet... OAuth-based roles are recommended") and was
  left disabled instead. What's actually running: a Databricks service
  principal (`relsun-backend`) mints short-lived OAuth access tokens via
  `client_credentials` grant against `{DATABRICKS_HOST}/oidc/v1/token`.
  `app/lakebase_auth.py` caches the token in memory and refetches within 5
  minutes of its ~1 hour expiry; `app/db.py`'s engine has a `do_connect`
  hook that calls it on every new physical connection, plus
  `pool_recycle=1800` so pooled connections don't sit on a dead token.
  `DATABASE_URL` therefore carries no password at all — just the service
  principal's Application ID as username; the real credential is minted
  at connect time, never stored. Alembic's `env.py` was changed to reuse
  `app.db.engine` rather than building a fresh one, since a separately
  built engine has no `do_connect` hook and fails with "no password
  supplied."
- **Not done as part of this pivot** (flagged, not built): no Unity
  Catalog Delta "bronze" landing of raw GLEIF XML. Databricks Apps hosting
  for FastAPI/Next.js followed separately and **is now live** — one
  combined app, browser-verified 2026-08-27; see **§8b** and
  `deploy-combined/DEPLOY.md`. (`backend/app.yaml` is the retired
  two-app config.)

---

## 4. Data Strategy (short version)

Real data, not synthetic, bulk-loaded broadly with processing done lazily
and narrowly:

- **~3.4M real entities**, **~257K real ownership edges** (originally
  ~169K at first load; the count changed after the §3a Databricks reload
  reprocessed the same source GLEIF ZIPs — not a new dataset), bulk-loaded
  from GLEIF's Level 1 (entities) + Level 2 (ownership) files — no
  hand-picked subset.
- Every record's `domain` is currently `"Party"` — GLEIF gives no other
  domain, and Item/Location domains are designed-for in the schema
  discussion below but not yet loaded with real data (see §12).
- The only intentionally fabricated data point is
  `relationship_status: existing_customer`-style product metadata layered
  on top of real entities — never invented ownership relationships.
- Embeddings are generated lazily, on first touch by a search or compare,
  never pre-computed in bulk.

Full detail: `DATA_STRATEGY.md`.

---

## 5. Master Data Search

**Route:** `/mdm/search` · **Endpoint:** `GET /search?q={query}&domain={domain?}`

Fuzzy, typo-tolerant search — not exact-match only. Implementation:
`backend/app/search.py`.

**Algorithm:** blocking (cheap, recall-oriented — Postgres `pg_trgm` +
`pgvector`) → composite scoring (Jaro-Winkler, trigram word similarity,
vector cosine similarity, phonetic/metaphone match) → threshold
(`SIMILARITY_THRESHOLD = 0.72`). Deliberately not vector-embeddings-alone
— that missed typo-style matches early on ("Boeng" didn't surface "The
Boeing Company" in the top 5 nearest neighbors by embedding alone).

Results come back tiered: **Exact** (literal name match, starts-with
match, or full-text-search whole-word match) always ranks above
**Similarity** (fuzzy match, with a 0–1 score) — this prevents a
coincidental substring match (e.g. "nike" hiding inside "kliniken") from
crowding out a real match.

Rarity-weighting is computed from real corpus statistics
(`word_frequencies` table, populated via Postgres's `ts_stat()`) rather
than a hardcoded stopword list — a common word like "LLC" or "Systems"
gets down-weighted based on how often it actually appears in the loaded
data, not a guess.

Soft-deleted records (`deleted_at IS NOT NULL` — see §9's Party Request
workflow) are excluded from every search.

**Real example** — searching `"Hanger"`:

| Entity Name                 | ID      | Domain | Match |
| --------------------------- | ------- | ------ | ----- |
| Hanger, Inc.                | 2076447 | Party  | Exact |
| HANGER SOLUTION             | 1729402 | Party  | Exact |
| HANGERLOGIC INC.            | 1191434 | Party  | Exact |
| HANGERWORLD LIMITED         | 6274    | Party  | Exact |
| HANGERS AUSTRALIA PTY. LTD. | 995593  | Party  | Exact |

Searching the deliberately-misspelled `"Hangr"` returns fuzzy matches
instead (no exact hits): `Hangren Oy` (id 2806737), `Hangret California
GmbH` (id 547861), `HANGROW FOODS INDIA PRIVATE LIMITED` (id 1318448),
`Hangry Holding UG` (id 607550), `Hangrove Terrace Partners Limited
Partnership` (id 1201634) — each labeled `Similarity` with a score.

---

## 6. Master Data Compare

**Route:** `/mdm/compare?ids={id}&ids={id}...` (2+ ids) · **Endpoints:**
`GET /compare` (deterministic) and `GET /compare/summary` (AI narrative,
separate/optional)

Implementation: `backend/app/compare.py`. Two independent things happen
here, deliberately kept apart:

### 6a. Deterministic comparison (`GET /compare`, always available, fast)

For each field present on any of the selected records' `attributes`
JSON, computes a per-field status: `match` (same value everywhere it's
present), `partial` (present on some records, missing on others), or
`conflict` (values disagree). Also computes a **pairwise verdict** per
pair of records — `Likely duplicate` / `Possibly related` / `Likely
distinct` — from name similarity signals only (Jaro-Winkler, trigram,
vector cosine, phonetic), **not** from the field diffs and **not** from
any relationship/ownership data.

**Real example** — comparing Hanger, Inc. (id 2076447) vs. HANGER
SOLUTION (id 1729402):

```json
{
  "records": [
    {
      "id": 2076447,
      "name": "Hanger, Inc.",
      "domain": "Party",
      "attributes": {
        "lei": "254900ZJJJYVLHJXSZ60",
        "country": "US",
        "city": "WILMINGTON",
        "hq_country": "US",
        "hq_city": "Austin",
        "legal_form": "XTIQ",
        "status": "ACTIVE",
        "source": "gleif"
      }
    },
    {
      "id": 1729402,
      "name": "HANGER SOLUTION",
      "domain": "Party",
      "attributes": {
        "lei": "9845005U295AEF9F6336",
        "country": "IN",
        "city": "Daman",
        "hq_country": "IN",
        "hq_city": "Daman",
        "legal_form": "A0PS",
        "status": "ACTIVE",
        "source": "gleif"
      }
    }
  ],
  "fields": [
    { "key": "lei", "status": "conflict" },
    { "key": "country", "status": "conflict" },
    { "key": "city", "status": "conflict" },
    { "key": "legal_form", "status": "conflict" },
    { "key": "status", "status": "match" },
    { "key": "source", "status": "match" }
  ],
  "pairwise": [
    {
      "record_a_id": 2076447,
      "record_b_id": 1729402,
      "score": 0.87,
      "verdict": "Likely duplicate",
      "signals": {
        "name_similarity": 0.87,
        "trigram_similarity": 0.636,
        "vector_similarity": 0.606,
        "phonetic_match": false
      },
      "rationale": "Likely duplicate (87% match): names are nearly identical character-for-character; substantial word overlap in the name."
    }
  ]
}
```

Notice the tension: the **verdict says "Likely duplicate" at 87%** purely
from name similarity, while the **field facts show a different LEI,
country, city, and legal form** — strong evidence these are two distinct
companies that happen to share wording. The deterministic layer surfaces
both; it's the AI summary layer (or the Compare Agent, §8) that has to
reason about the tension rather than just repeating the verdict.

### 6b. AI-drafted summary (`GET /compare/summary`, optional, slower)

A leaf agent (`compare_summary_agent`, see §8.6) drafts a plain-English
narrative over the deterministic output above — never recomputes
anything, never sees raw records beyond what `compare.py` already
extracted.

**Real example output** for the same pair:

> "The records **Hanger, Inc.** and **HANGER SOLUTION** show an 87% name
> match but have fundamentally conflicting location and identifier data:
> one is registered in the US (Wilmington/Austin) with a specific LEI,
> while the other is registered in India (Daman) with a different LEI
> and legal form. Before proceeding, a data steward should verify whether
> these are genuinely the same company with multiple registrations in
> different countries, or distinct entities that happen to share similar
> names — checking the LEI assignments and company incorporation records
> will be critical to resolving this discrepancy."

---

## 7. View Graph (Relationship Intelligence)

**Route:** `/mdm/graph?id={record_id}&hops={1|2|3}` · **Endpoint:** `GET
/graph/{record_id}?hops={n}&limit={n}`

Implementation: `backend/app/graph.py` (iterative BFS over a plain
Postgres `relationship_edges` table, since the Platform Pivot in §3a
replaced Neo4j — see below) + `frontend/src/components/mdm/RelationshipGraph.tsx`
(custom SVG, **d3-force used for physics only** — dragging/pan/zoom are
plain React pointer events, not d3-drag/d3-zoom, to avoid the classic
React/D3 DOM-ownership conflict).

**Why custom, not Neo4j Bloom (still the right call post-pivot):** Bloom
needed a paid Enterprise/Aura tier, and — more importantly — is a closed
third-party tool with no way to inject the "act on this relationship →
create a Master Data Request" button the product's whole flagship
narrative depends on. Moving off Neo4j entirely didn't reopen this
question — the rendering was always custom SVG regardless of what stored
the graph underneath it.

**How the BFS works:** starting from the anchor id, each round trip pulls
every `relationship_edges` row touching the current frontier (`parent_id
= ANY(:frontier) OR child_id = ANY(:frontier)`), unions in the newly
discovered ids, and repeats up to `hops` times (1–3, `DEFAULT_HOPS = 2`).
Undirected on purpose, same as the Neo4j Cypher this replaced — a
different tenant's data may care about ownership in either direction from
a given anchor. `limit` (`DEFAULT_PATH_LIMIT = 80`) caps the total number
of *nodes* admitted, not path count (unlike the old Cypher, which could
bound paths directly) — that's what actually protects against a
high-fan-out hub entity blowing up the response; `truncated: true` comes
back on the `GraphResponse` when it kicks in. Every relationship type is
supported (`type` is a free string on the edge, not hardcoded to `OWNS`)
even though GLEIF-sourced data only ever produces `OWNS` today.

**Real example** — centered on "Standard Bank Group Limited" (id
1842436), 2 hops: **40 entities, 47 relationships**, all typed `OWNS`,
including subsidiaries like Stanbic Bank S.A., SBG Securities Proprietary
Limited, Standard Bank Namibia, Standard Lesotho Bank Limited, and
~30 more across multiple African countries — rendered as a force-directed
graph with the anchor node larger/highlighted and arrows pointing
owner → subsidiary.

**Known gap:** the flagship "Hanger → owned by Patient Square → Patient
Square also owns Boeing (existing customer)" story from the wireframe is
a **hypothetical illustrative narrative**, not real loaded data — the
real Hanger, Inc. record has zero edges in the real ownership graph
(ownership data is real but sparse; ~257K edges post-reload, see §3a).
Don't demo that exact story as if it's live data.

### 7a. Interaction polish (MarketGraph-parity pass, 2026-08-26)

Three additions to the graph view, done in the same pass as the Graph
Context sub-agent (§8.8) — the explicit goal was interaction parity with
MarketGraph's click-to-inspect pattern **without** sidelining the Data
Concierge, since the graph rendering isn't Relsun's differentiator, the
agent layer is.

- **Click-to-focus + side panel.** Clicking a non-anchor node no longer
  immediately recenters the graph — it *selects* the node: every
  node/edge outside its immediate neighborhood dims (`opacity`), and a
  new side panel (`frontend/src/components/mdm/GraphNodeDetail.tsx`,
  styled to match `RecordPanelTray.tsx`'s header/`dl`/footer conventions)
  shows its name, domain, LEI, `existing_customer` flag, and connectivity
  (below). Footer actions: **Recenter graph here** (the old click
  behavior, now explicit and opt-in) and **Open record** (reuses
  `useRecordModal()`, the same modal Search and Concierge record links
  already open). Clicking empty canvas, or re-clicking the selected node,
  clears the selection.
- **Connectivity signal.** Purely client-side — node degree is a count of
  `data.edges` touching that node's id, computed from the `GraphResponse`
  the page already fetched. Shown in the side panel as "Connections in
  this view." No backend change; not the record's true total connection
  count, only what's visible at the current hop radius.
- **Always-on legend.** Previously the top-left banner only appeared when
  every edge in the graph happened to be the same type (`isUniform`) — a
  first-time viewer got nothing to explain the styling otherwise. Now a
  persistent legend always shows: the anchor ring style, the
  existing-customer dashed amber ring, and a per-domain color key
  (reusing `domainNodeFill` from `Badges.tsx`).

Explicitly not built in this pass (flagged as a possible future one):
"Expand" — merging a second node's full neighborhood into the current
view without recentering.

---

## 8. The Agent Architecture

### 8.1 The shared framework

Every agent is an instance of one shared class
(`backend/app/agents/framework.py`), not a bespoke implementation each
time.

```python
@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict   # JSON Schema, Anthropic tools= format
    handler: Callable[..., str]

@dataclass
class Agent:
    name: str
    instructions: str    # plain English — the entire "configuration" surface
    tools: list[Tool] = field(default_factory=list)
    model: str = ""       # falls back to settings.anthropic_model
```

**`Agent.run(prompt, *, client=None, context=None, history=None)`** — the
tool-use loop: calls `client.messages.create(system=instructions,
tools=[...], messages=[...])`; if the model's `stop_reason` is
`"tool_use"`, it dispatches to the matching `Tool.handler`, appends the
result, and loops (capped at `MAX_TOOL_TURNS = 6` so a bad
instruction/schema mismatch fails fast rather than looping forever
burning tokens); otherwise it returns the model's final text.

**`agent_as_tool(agent, *, name, description)`** — wraps a child
`Agent.run()` as a callable `Tool` for a parent agent, propagating the
same client and ambient context (e.g. the DB session) down. This is the
literal mechanism behind "an agent's tools can include other agents."

**Handler convention:** every `Tool.handler` is called as
`handler(**tool_input, **context)`. `context` always includes `client`
(so `agent_as_tool` can propagate it to a child) plus whatever the
top-level caller passed in — currently just `session` (the DB session).
Handlers declare the context keys they use as named parameters and
accept `**_ignored` for the rest.

**Mocked test coverage** (`backend/tests/test_agent_framework.py`, 4
tests, $0 — a scripted fake `Anthropic` client, no real API calls):
no-tool-call happy path, single tool-call-then-answer, a full multi-hop
agent-calls-agent chain (verifying client/context propagation), and the
turn-cap safety valve.

### 8.2 The hierarchy, visually

```
Data Concierge Agent                        (top-level, entry point)
  └─ master_data  ─→  Master Data Handling Agent
                         ├─ master_data_search         ─→ Master Data Search Agent
                         ├─ master_data_compare        ─→ Master Data Compare Agent
                         │                                  └─ draft_compare_summary ─→ Compare Summary Agent (leaf)
                         ├─ master_data_request        ─→ Party Request Agent
                         │                                  └─ get_recommendation ─→ Recommendation Agent (leaf, real web search)
                         └─ master_data_graph_context  ─→ Graph Context Agent (leaf)
```

Every arrow is `agent_as_tool()`. Nothing above is a fixed sequence —
which arrow (if any) gets followed for a given prompt is decided by each
agent's own instructions, at runtime, from what the prompt actually says.
Added since the 2026-08-13 snapshot: `get_recommendation` (2026-08-20,
§8.10) and `master_data_graph_context` (2026-08-26, §8.11).

### 8.3 Trigger — how any of this actually starts

**Every path starts the same way:** `POST /concierge/chat` →
`concierge_agent.run(prompt, context={"session": session}, history=[...])`.
There is no other entry point into the agent hierarchy. `history` is a
list of prior `{role, content}` turns — held client-side by the frontend
and resent each turn (not server-side persistent memory; see §12's open
questions). Three real-world ways a prompt reaches this endpoint:

1. **Typed chat** — the Data Concierge screen (`/`).
2. **A UI-action-generated prompt** — e.g. Search's "Create as new Party
   record" link on a no-results page deep-links to `/?prompt=...`, which
   auto-sends that exact text as if the user typed it.
3. _(Designed, not built)_ a schedule-generated prompt — e.g. a daily
   downstream-publish run. No scheduler exists yet (§12).

### 8.4 Data Concierge Agent

**File:** `backend/app/agents/concierge_agent.py` · **Model calls per
turn:** 1+ (at least one to decide whether to hand off, plus however many
its sub-agent chain takes)

**Purpose:** entry point. Interprets the prompt, decides which module
it's about, hands off with a self-contained request. Also the **only**
agent that ever sees raw conversation history — it's responsible for
resolving references ("it", "that company") before handing off, since
child agents never see history, only whatever prompt string the
Concierge composes for them.

**Tools:** one — `master_data` (→ Master Data Handling Agent).

**Full instructions (verbatim):**

> "You are the Data Concierge, the entry point for an AI-native MDM
> (master data management) platform. Right now the only module available
> to you is Master Data (covering Party, Item, and Location entities) —
> hand off to it via the master_data tool for anything about searching,
> comparing, or creating/updating/deleting master data records (note: as
> of now, searching, comparing, and Party create/update/delete requests
> are implemented underneath it — Item and Location requests are not yet,
> and no request is ever actually applied until a human approves it in
> the Review Queue; the Master Data agent itself will tell you if
> something goes beyond what's available). Data Catalog, Data Governance,
> and Data Quality are not built yet; if a request is clearly about one
> of those (e.g. glossary terms, data policies, quality rules), say
> plainly that module isn't available yet rather than guessing or
> pretending to help with it. Before asking the user to clarify, check
> the conversation history for what a reference like 'it', 'that
> company', or 'the second one' points to — e.g. if you just told the
> user a record's name and ID, a follow-up saying 'compare it with X'
> means that same record. The master_data tool only sees the
> self-contained request you send it, not the conversation history, so
> once you've resolved a reference, state it explicitly in what you hand
> off (e.g. 'compare Hanger Inc (id 2076447) with Hanger Solution'), not
> 'it'."

**Real example — pronoun resolution across turns:**

| Turn | Input                                          | Output                                                                                                                                         |
| ---- | ---------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | "Does Hanger Inc already exist in our system?" | "Yes, Hanger Inc already exists in your system! ... Record ID: 2076447 ... Status: Exact match (100% confidence) ..."                          |
| 2    | "compare it with Hanger Solution"              | _(with turn 1's history attached)_ → correctly resolved "it" = Hanger Inc, id 2076447, and produced a full compare result — see §8.5's example |

_(This took an actual instruction fix to get right — the first version of
the Concierge's instructions asked for clarification instead of checking
history. See §12 "Real bugs found by testing.")_

### 8.5 Master Data Handling Agent

**File:** `backend/app/agents/master_data_agent.py`

**Purpose:** module-level router for Master Data. Also the **bridge**
between name-based user language and ID-based tool requirements: Compare
and Request both need record IDs, not names, so when a prompt only gives
a name, this agent calls Search first, then hands the resolved ID to
whichever sub-agent actually needs it. Nothing hardcodes that two-step
order.

**Tools:** four — `master_data_search`, `master_data_compare`,
`master_data_request`, and (added 2026-08-26) `master_data_graph_context`
(§8.11).

**Full instructions (verbatim, current):**

> "You are the Master Data Handling Agent for an MDM (master data
> management) platform, covering the Party, Item, and Location domains.
> You have four sub-agents available:
>
> master_data_search — looks up whether an entity already exists (search
> by name, fuzzy/typo-tolerant, optionally filtered to a domain).
>
> master_data_compare — evaluates whether specific records, by ID not
> name, are duplicates, related, or distinct. If asked to compare records
> by name, first use master_data_search to resolve each name to an ID,
> then call master_data_compare with those IDs.
>
> master_data_request — for Party records only (customers, suppliers,
> third parties); Item and Location aren't supported yet. Handles
> proposing a create, update, or delete — it never applies anything
> itself, only submits a pending proposal for review. Update and delete
> need a record ID, not just a name: if the user only gave a name, use
> master_data_search to resolve it first, the same way you do for
> compare. A create needs no prior ID.
>
> master_data_graph_context — use this when the user is clearly asking
> about relationships or entities in a relationship graph currently on
> their screen (e.g. 'why is this connected to X', 'summarize this',
> 'which of these is the parent') rather than asking you to look
> something up fresh. It only knows the exact view the user currently has
> open, not the full graph — if the user's question reaches beyond that,
> prefer master_data_search or say plainly the answer isn't in the
> current view.
>
> None of your sub-agents can approve or reject a pending request — that
> only happens when a human reviews it in the Review Queue screen. If
> asked to approve/reject/finalize something, say plainly that has to
> happen there, not here.
>
> A sub-agent's reply may already contain markdown links in the form
> [Name](record:ID) — that's how a specific record gets turned into
> something clickable for the person you're relaying to. Preserve that
> exact [Name](record:ID) formatting for any record you mention in your
> own reply, whether you're passing a sub-agent's link through unchanged
> or restating a record you know the id of yourself — never flatten it to
> plain text like 'Name (ID: 123)'."

(The last two paragraphs — graph context routing and link-preservation —
were both added after the 2026-08-13 snapshot; the markdown-link
convention exists because §8a's `PartyDetailModal` needs a stable scheme
to intercept.)

**Real example — resolving a name to an ID before comparing:** prompt
"compare Hanger Inc and Hanger Solution - are they the same company?"
triggers, in order: `master_data_search("Hanger Inc")` → 2076447,
`master_data_search("Hanger Solution")` → 1729402, then
`master_data_compare([2076447, 1729402])`. Full chain took **~31
seconds** (4 sequential LLM-backed hops) and produced:

> "Based on the comparison, **Hanger Inc and Hanger Solution are NOT the
> same company.** They are distinct, separate organizations: **Different
> Legal Entities** – completely different LEIs ... **Different
> Countries** – US (Austin, TX) vs. India (Daman) ... **Different Legal
> Forms** ... While they share a similar name, the regulatory and
> organizational data clearly establishes they are two independent
> companies with no apparent connection."

Note it correctly overrode the raw 87%-"Likely duplicate" verdict using
the field facts, and correctly declined to claim any ownership
relationship (it has no graph access — see §8.6).

### 8.6 Master Data Search Agent

**File:** `backend/app/agents/search_agent.py`

**Purpose:** thin wrapper around the deterministic `search_master_records`
(§5) — one tool, no judgment beyond "did I search yet."

**Tools:** one — `search_master_data`, wrapping `search_master_records(session, query, domain)`.

**Full instructions (verbatim):**

> "You are the Master Data Search Agent for an MDM (master data
> management) platform. You have one tool, search_master_data, which
> searches the platform's internal master records by name. It returns
> 'Exact' matches (the name literally matches) and 'Similarity' matches
> (fuzzy/typo-tolerant, each with a 0-1 score), optionally restricted to
> one domain (e.g. 'Party'). Always call the tool before answering any
> question about whether an entity exists or what matches a name — never
> guess or answer from memory. Report results plainly: which records were
> found, their match type and score, and their domain. If nothing is
> found, say so directly. You cannot create, update, or delete records,
> and you have no other data source beyond this internal search — if
> asked for something outside that, say plainly that it isn't available
> yet rather than attempting it."

**Deliberate omission:** the founders' original spec describes this
agent also triggering an "AI web-search check" when nothing is found
internally. No such tool exists, so the instructions above **don't
mention it** — an agent's instructions should never describe a capability
its tools can't back up.

### 8.7 Master Data Compare Agent

**File:** `backend/app/agents/compare_agent.py`

**Purpose:** wraps the deterministic compare engine (§6a) as a tool, plus
the summary leaf agent (§6b/8.8) as a second tool, and decides when a
narrative is actually worth drafting.

**Tools:** two — `compare_master_data` (wraps `compare_records` + `render_compare_facts`),
`draft_compare_summary` (`agent_as_tool` → Compare Summary Agent).

**Full instructions (verbatim):**

> "You are the Master Data Compare Agent for an MDM (master data
> management) platform. You have two tools: compare_master_data, which
> takes 2 or more record IDs and returns deterministic field-by-field
> differences and a pairwise verdict (Likely duplicate / Possibly related
> / Likely distinct, with a score and a stated reason); and
> draft_compare_summary, which turns comparison facts you already have
> into a short plain-English narrative — pass it the exact output of
> compare_master_data, verbatim, as its prompt. Always call
> compare_master_data first. Only call draft_compare_summary afterward if
> a narrative genuinely helps (e.g. several fields differ, or more than
> two records were compared) — for a simple check, the verdict alone is
> often enough. Never state a verdict or cite a difference
> compare_master_data didn't actually report. The verdict measures name
> and field similarity only — it says nothing about ownership or
> corporate relationships. If the field-level facts (e.g. different LEI,
> different country) point away from the name-similarity verdict, say so
> plainly rather than leading with the verdict alone. Never claim two
> entities are related through ownership, a parent company, or any other
> relationship — you have no access to that data."

That last sentence is load-bearing: **this agent has no relationship-graph
access.** Relationship-based "these might be connected through an
ownership chain" reasoning belongs to the Graph Context Agent (§8.11,
grounded only in whatever's currently on screen) and the still-unbuilt
full Recommendation Agent vision (§8.10/§12), not this one.

### 8.8 Compare Summary Agent (leaf)

**File:** `backend/app/agents/compare_summary.py`

**Purpose:** the only agent with **zero tools** — pure text drafting over
facts it's handed. Reused two ways: directly by `GET /compare/summary`
(no agent hierarchy involved, called synchronously from `main.py`) and
indirectly as a tool the Compare Agent can call mid-conversation.

**Full instructions (verbatim):**

> "You are a master data comparison assistant for an MDM (master data
> management) platform. You will be given structured, already-computed
> field-level differences and match-verdict data for a set of records.
> Write a concise summary, about 3 sentences, in plain English,
> highlighting the key differences and what a data steward should look at
> first. Only describe what is in the provided data — never invent facts,
> and never recommend merging, deleting, or overwriting any record; you
> are drafting a summary for a human to review, not taking an action."

### 8.9 Party Request Agent

**File:** `backend/app/agents/party_request_agent.py`

**Purpose:** gathers what's needed for a create/update/delete of a
**Party** record conversationally, then saves it as a pending proposal.
**Cannot write to `master_records` under any circumstance** — the only
thing it can do is call a tool that inserts a `pending`-status row.

**Tools:** three —

- `submit_party_request` (plain deterministic tool, wraps
  `requests.submit_request`)
- `check_request_status` (plain deterministic tool, read-only, wraps
  `requests.get_request`/`list_requests`)
- `get_recommendation` (added 2026-08-20 — `agent_as_tool` → Recommendation
  Agent, §8.10; a real sub-agent hop, not a plain tool)

No Search/Compare access is wired in here directly (this agent still
can't resolve a bare name to an ID itself — that's the Master Data
Handling Agent's job, §8.5).

**Full instructions (verbatim):**

> "You are the Party Request Agent for an MDM (master data management)
> platform. Your job is to gather what's needed to propose a create,
> update, or delete of a Party record (customers, suppliers, third
> parties), then submit it — you never approve, reject, or write directly
> to master data yourself. Every request you submit lands as pending in
> the Review Queue, and only becomes real once a human reviews it there.
>
> For a CREATE: name and country are both REQUIRED — do not submit
> without both, ask if either is missing. LEI is optional, but if the
> user gives one, include it: it's checked against every existing record,
> and submission will be rejected if it's already in use (that means this
> is the same legal entity, not a new one — tell the user that plainly
> rather than retrying). Ask for other relevant fields too (e.g. city)
> but don't demand an exhaustive form beyond name/country. When you need
> several fields at once, ask for them in one compact list (e.g. 'Name,
> Country, City, LEI (optional)?') rather than one at a time, to keep the
> exchange short.
>
> For an UPDATE or DELETE: you need the target record's ID. If the user
> only gave a name, you cannot look it up yourself — say so and ask for
> the ID, or ask them to search for it first. Never guess an ID. An
> update that changes the LEI is checked the same way a create is —
> rejected if that LEI already belongs to a different record.
>
> Once you have what you need, call submit_party_request. If it reports a
> validation problem (missing field, or a duplicate LEI), relay that
> reason to the user plainly — don't retry blindly. After a successful
> submit, tell the user plainly that it's pending review — not done, not
> applied. Use check_request_status to answer questions about a request's
> current state; you cannot change that state yourself, only report it.
> Beyond an exact LEI match, you have no way to check whether a proposed
> record might be a duplicate of something existing — don't claim to have
> checked beyond that."

**Real example — create, with the agent correctly refusing to proceed on
name alone:**

Prompt: _"create a new party record named Brenwick Analytics"_
Response: _"I've started the process to create a new party record for
**Brenwick Analytics**. To complete the request, I need one required
piece of information: **Country** – Which country is Brenwick Analytics
based in? Once you provide that, I can finalize the proposal and send it
to the Review Queue. If you have any additional details like the city,
LEI number, or other party attributes, feel free to share those as
well!"_

**Real example — full create → submit:**

Prompt: _"Create a new Party record named 'Quorvath Dynamics'"_
Response (turn 1): asked for Country (required), City (optional), Party
Type
Prompt (turn 2): _"Country US, City Denver, Party Type Supplier"_
Response: _"Perfect! I've submitted your request to create a new Party
record for **Quorvath Dynamics** as a Supplier in Denver, US. **Request
ID: 27** has been sent to the Review Queue for approval..."_

**Real example — update, resolved by name via the Master Data Agent's
Search bridge:**

Prompt: _"update Quorvath Dynamics's city to Boulder"_
Response: _"Done! I've submitted an update request for Quorvath Dynamics
to change their city to Boulder. The request (Request #28) is now
waiting for human review..."_
→ Verified: `GET /requests/28` showed `"target_record_id": 3399233,
"proposed_attributes": {"city": "Boulder"}` — correctly resolved from
name to the actual ID.

**Real example — delete:**

Prompt: _"delete the Quorvath Dynamics record"_
Response: _"Done! I've submitted a delete request for the Quorvath
Dynamics record (ID: 3399233). It's now request #29..."_

### 8.10 Recommendation Agent (leaf, built 2026-08-20)

**File:** `backend/app/agents/recommendation_agent.py`

**Purpose:** Party's recommendation sub-agent from the original
graph-aware, sales-acceleration vision — deliberately narrow first slice.
Given a company name, it runs a **real live web search** (Anthropic's
server-side `web_search_20260209` tool, not a client tool this repo
implements) for firmographic facts — principally HQ address and
legal/trading name — and returns them as an unverified suggestion for
`party_request_agent` to relay, never something written to
`master_records` directly.

**Tools:** one — a raw server-side tool (`WEB_SEARCH_TOOL`, `max_uses: 5`),
not a normal `Tool` with a Python handler. This required two additions to
`agents/framework.py` that didn't exist at the 2026-08-13 snapshot:
`Tool.raw_schema` (server tools use a `type` + params shape, not
name/description/input_schema) and `pause_turn` handling in the run loop
(a long server-tool turn can pause mid-search with no client tool
awaiting a result — previously indistinguishable from a final answer,
which would have raised on an empty text block).

**Full instructions (verbatim):**

> "You are the Recommendation Agent for an MDM (master data management)
> platform's Party domain. Given a company name (and whatever other
> details you're given), use web search to find real, current, verifiable
> facts about it that would help someone filling in a Party record —
> principally its headquarters address (street, city, state/region,
> country) and legal/trading name, plus anything else clearly relevant
> (industry, other office locations) if it comes up naturally in the
> search results.
>
> You have web search only right now — no access to the internal master
> data graph and no D&B lookup, so you cannot say whether an entity
> already exists in Relsun or is connected to one that does; don't imply
> otherwise.
>
> Always phrase findings as a suggestion sourced from a live web search,
> not a stated fact — the calling agent still has to offer it to a human,
> and nothing you find is written to master data by you or anyone
> downstream without a human approving it. If search turns up nothing
> solid or the results conflict, say that plainly rather than guessing an
> address. Be concise — a short list of fields and values, not a research
> report."

**Real example — end to end, live-verified:** asked to create a Boeing
party record with only the name known, `party_request_agent` called
`get_recommendation`, which ran a real web search and returned Boeing's
actual current HQ (**Arlington, VA** — correctly reflecting its real
2022 relocation from Chicago) plus a real LEI, both explicitly flagged as
unverified and offered for confirmation rather than submitted outright.

**Not built** (deliberately deferred, not a gap in this slice): the
internal-graph lookup ("memory before Google" — see §1's lookup design
principle), D&B, and the full ownership-chain / parent-child-location
recommendation flow (e.g. proposing a linked HQ + branch pair) from the
original vision.

### 8.11 Graph Context Agent (leaf, built 2026-08-26)

**File:** `backend/app/agents/graph_context_agent.py`

**Purpose:** lets the Data Concierge answer questions grounded in the
*exact* relationship graph currently rendered on the user's screen — "why
is this connected to Boeing," "summarize this cluster" — rather than
falling back to a generic re-search or, worse, guessing from general
knowledge. Modeled directly on the Search Agent's one-tool pattern
(§8.6): always call the tool first, answer only from what it returns.

The graph payload never comes from a fresh DB query inside this agent —
the frontend already fetched it (`GraphResponse`, via `GET
/graph/{id}`, §7) to render the page, and resends that exact object as
`graph_context` on the chat request (`ConciergeChatRequest.graph_context`,
`schemas.py`). This also means its answers are always about *this
specific view* (the hop radius currently open), not the record's full
graph — asked about something outside what's shown, it says so rather
than guessing.

**Tools:** one — `get_graph_context`, reading `graph_context` from the
ambient `context` dict (the same `Tool.handler(**tool_input, **context)`
mechanism `session` already uses, §8.1) and rendering it into text:
anchor name/id, which visible entities are flagged `existing_customer`,
and each relationship touching the anchor described the same
direct-vs-ultimate-parent way `RelationshipGraph.tsx`'s `edgeLabel()`
already phrases it on screen, so the Concierge's wording matches what the
user is looking at.

**Full instructions (verbatim):**

> "You are the Master Data Graph Context Agent for an MDM (master data
> management) platform. You have one tool, get_graph_context, which
> describes the relationship graph currently displayed on the user's
> screen — always call it first, before answering anything. Answer using
> only what it returns: if a relationship, node, or entity isn't
> mentioned in that description, say plainly that it isn't visible in the
> current view (e.g. 'not shown at the current hop radius') rather than
> guessing or falling back to general knowledge. If the tool reports no
> graph is currently displayed, say so directly — don't attempt to
> describe a graph from memory of the conversation. When you reference a
> specific record, format it as a markdown link in the exact form
> [Name](record:ID), matching how the other Master Data sub-agents
> already do this."

**The real bug this build hit, and the actual fix** (a prompting lesson,
not a wiring bug — worth internalizing for any future routing
instruction added to this hierarchy): after wiring everything above
correctly (confirmed via temporary trace logging that the right
`GraphResponse` reached the backend every time), the **Concierge Agent's
own top-level call** (§8.4) still returned `stop_reason=end_turn` for
graph questions — it never even attempted `tool_use` on `master_data`.
Mentioning graph questions as one clause inside a longer descriptive
sentence in `CONCIERGE_INSTRUCTIONS` did **not** fix it. What did:
rewriting that guidance as a short, separate, imperative paragraph that
(a) lists concrete trigger phrases ("this", "here", "on screen",
"connected"), (b) says **ALWAYS hand off, even if you don't think you
have a way to answer it**, and (c) explicitly forbids the top-level agent
from concluding on its own that it lacks the capability — "that
determination belongs to master_data." An LLM router will silently
self-reject a hand-off it isn't confident about unless told point-blank
not to make that judgment call itself.

**Real example — live-verified, on `/mdm/graph` centered on The Boeing
Company:** prompt _"what does the current graph show?"_ →
_"The current graph is centered on THE BOEING COMPANY, the anchor, which
is flagged as an existing customer. It's the only entity in the graph
with that flag — none of the related entities carry it. The graph shows
6 entities total, all connected to the anchor via direct..."_ — correctly
grounded in the real on-screen data, not a generic answer. Also verified
the negative case: navigating away from the graph page and asking a
follow-up graph question gets "No graph is currently displayed" rather
than stale context carried over from the page just left.

**Frontend plumbing:** `frontend/src/lib/chat.tsx`'s `ChatProvider` holds
`graphContext` state and a `setGraphContext` setter; `app/mdm/graph/page.tsx`
pushes the current `GraphResponse` into it via `useEffect` on every fetch
and clears it (`setGraphContext(null)`) on unmount, so the Concierge only
"sees" a graph while one is actually on screen and always the current
one. See §7a for the graph-interaction polish done in the same pass.

---

## 8a. Authentication & Users (built 2026-08-14, header-routing corrected since)

There was **no auth system at all** in the 2026-08-13 snapshot — every
request was anonymous and the Review Queue was a single unattributed
list. Built per direct instruction, specifically to support a real
multi-user request/approval loop (submit as one person, log out, log in
as someone else, approve from the Review Queue).

- **`backend/app/auth.py`:** stdlib PBKDF2-HMAC-SHA256 password hashing
  (`hashlib`, constant-time compare via `hmac.compare_digest` — no
  bcrypt/passlib dependency added, since this is a handful of internal
  demo users, not a public signup surface) and opaque, server-side
  session tokens (`user_sessions` table, 12-hour TTL) rather than a JWT —
  the entire point being that `POST /auth/logout` can actually revoke a
  session, not just have the client discard a self-contained token that
  stays valid regardless.
- **Every API route requires a valid session token** except `/health` and
  `/auth/login`, enforced via `get_current_user` (`backend/app/deps.py`).
- **Header correction (found while prepping the Databricks Apps hosting,
  after the 2026-08-14 build):** the token does **not** travel as the
  standard `Authorization` header — it travels as a custom
  `X-Relsun-Token` header. Databricks Apps' own gateway reserves
  `Authorization` for its own OAuth session validation and silently
  strips/rejects anything it can't validate as a Databricks token before
  the request ever reaches this app. This was discovered live: every
  authenticated call 401'd with no `Authorization` header visible
  server-side at all, even immediately after a successful same-origin
  login. `frontend/src/lib/api.ts` sends `X-Relsun-Token`; any
  curl/script-based testing against this API must do the same.
- **Actor identity on requests:** `MasterDataRequest` gained
  `submitted_by`/`decided_by` FKs to a new `users` table — two separate
  columns, not one shared "actor," since the submitter and decider are
  commonly (by design) different people. The logged-in user chatting with
  the Concierge threads into `party_request_agent`'s submit tool via
  `context["current_user_id"]`; the logged-in user calling `POST
  /requests/{id}/approve`\|`reject` is recorded as decider.
- **Frontend:** `/login` page + `lib/auth.tsx`'s `AuthProvider`
  (localStorage-persisted token) + `AppShell` gating every other route
  client-side (this whole app is a client-rendered SPA-style Next.js
  frontend, no server auth/middleware). Sidebar shows "Signed in as X ·
  role" with a logout control.
- **Two demo users only** (no self-service signup), seeded via
  `backend/scripts/seed_users.py`:

  | Username | Password  | Display Name | Role         |
  | -------- | --------- | ------------ | ------------ |
  | `alice`  | `alice123`| Alice        | Sales Rep    |
  | `bob`    | `bob123`  | Bob          | Data Steward |

  `role` is a **display label only** — not an enforcement mechanism.
  RBAC (per-role permissions on who can approve what) is still explicitly
  not built (§12).
- **Live-verified end to end:** Alice submits a request via chat → logs
  out → Bob logs in → sees it in the Review Queue with "Requested by:
  Alice" → approves → the request shows "Decided by: Bob."
- **Record markdown links:** as part of the same build, Search/Compare/
  Party Request agent instructions started formatting any record they
  reference as `[Name](record:ID)`. `frontend/src/components/mdm/Markdown.tsx`
  intercepts that scheme via a custom `urlTransform` (react-markdown's
  default one silently blanks non-standard URI schemes) and opens a
  record detail panel in place via a shared `RecordModalProvider` context
  — no page navigation. The same mechanism backs Search's "open record"
  button, a "View record" link on Requests rows, and (§7a) the graph
  side panel's "Open record" button.

---

## 8b. Databricks Apps Hosting (built 2026-08-26, browser-verified 2026-08-27)

Full detail lives in [`deploy-combined/DEPLOY.md`](./deploy-combined/DEPLOY.md);
this is the summary.

**One app, both halves.** Relsun runs as a single Databricks App
`relsun-frontend` (`https://relsun-frontend-7474659130414957.aws.databricksapps.com`).
`start.sh` runs `uvicorn app.main:app` on `127.0.0.1:8001` in the
background and `exec`s `node server.js` (Next.js standalone) on
`$DATABRICKS_APP_PORT`. `next.config.ts` rewrites proxy `/auth /search
/compare /concierge /requests /graph /domains /health /master-records`
from the Next server to FastAPI on `:8001` — that hop stays inside the
container, so Databricks' per-app OAuth SSO gate never sees it. The
earlier two-app split (`relsun-backend` + `relsun-frontend`) is dead: a
browser `fetch` from one app to another can't complete the SSO redirect.

### 8b.1 Starting the app for a demo (the runbook)

**If it's already running:** open
`https://relsun-frontend-7474659130414957.aws.databricksapps.com`.
Workspace SSO logs you in, then the Relsun login takes `alice`/`alice123`
or `bob`/`bob123`. Nothing else to do.

**If it's been idle (the usual case — compute auto-stops to save money):**

- *CLI (fastest, one command):*
  `databricks apps start relsun-frontend --profile relsun` — starts compute
  **and** redeploys in one step. Then
  `databricks apps get relsun-frontend --profile relsun` until
  `app_status.state` is `RUNNING`.
- *Portal:* workspace URL → left sidebar **Compute → Apps** (or search
  `relsun-frontend`) → open the app → if status is *Stopped*/*Unavailable*,
  click **Deploy** (source-code path is pre-filled:
  `/Workspace/Users/medhanshrajdeo@gmail.com/relsun-frontend`) → watch the
  **Deployments** tab for *"App started successfully"*.

Either way the build takes **~6 minutes** (it downloads PyTorch for the
search embeddings). **Budget ~10 min before a demo** if the app has sat
unused. Then smoke-test: log in as `alice`, search "Hanger", open the
graph on The Boeing Company.

**Sharing with another person:** they must be a user in this Databricks
workspace (add them under **Settings → Identity and access → Users** —
needs workspace-admin). Then on the `relsun-frontend` app page →
**Permissions** → add their email → **Can use**. Send them the app URL;
they hit Databricks SSO first, then the Relsun `alice`/`bob` login.

**Checking status without the portal:**
`databricks apps get relsun-frontend --profile relsun -o json` — look at
`app_status.state` (want `RUNNING`) and `active_deployment.status.state`
(want `SUCCEEDED`). `databricks apps logs relsun-frontend --profile relsun`
streams the build + runtime log.

### 8b.2 Rebuild + redeploy (only when frontend/backend code changed)

1. `bash deploy-combined/build.sh` — rebuilds the bundle from `frontend/` +
   `backend/` source with `NEXT_PUBLIC_API_BASE_URL=same-origin`, and fails
   if `localhost:8000` leaks into the client bundle.
2. `MSYS_NO_PATHCONV=1 databricks sync --full deploy-combined <ws-path>
   --profile relsun --include '.next/**' --include 'node_modules/**'` — the
   two `--include` flags are **mandatory**: `databricks sync` honours the
   repo-root `.gitignore` (which ignores `.next/` and `node_modules/`), so
   without them it silently skips the whole built frontend and you
   redeploy the old bundle.
3. `MSYS_NO_PATHCONV=1 databricks apps deploy relsun-frontend
   --source-code-path <ws-path> --profile relsun`.
4. Sanity check before/after:
   `databricks workspace export <ws-path>/.next/BUILD_ID` must equal
   `cat deploy-combined/.next/BUILD_ID`.

`server.js`, `.next/`, `node_modules/`, `public/` in `deploy-combined/` are
build output — never hand-edit them; edit `app/`, `alembic/`, `scripts/`,
`requirements.txt`, `app.yaml`, `start.sh`.
**`deploy-combined/package.json` is special:** keep it minimal with **no
`scripts` block** — Databricks Apps' Node buildpack runs `scripts.build` if
present, and the standalone `package.json` Next emits carries
`"build": "next build"`, which then dies server-side against the pruned
`node_modules` (`Can't resolve 'react-dom/client'`). `build.sh` leaves this
file alone and asserts it has no `"build"` key.

### 8b.3 Idle auto-stop

On the current tier the App's compute stops after inactivity, and that
*clears the active deployment* — it needs a redeploy, not just a restart.
`databricks apps start relsun-frontend` does both. An error in the browser
after the app has sat unused is almost always this, **not** a data or code
problem.

### 8b.4 Lakebase visibility gotcha

`databricks database list-database-instances` returns empty and
`get-database-instance relsun-db` says "Resource not found" even while
Lakebase is perfectly healthy — that CLI view just doesn't surface this
instance. Check DB health by connecting (mint an OAuth token via the
`relsun-backend` service principal, `psycopg.connect` to the endpoint in
`DATABASE_URL`), never by trusting that listing. As of 2026-08-27 the DB
holds ~3.4M `master_records` and ~169K `relationship_edges`, intact.

### 8b.5 The `NEXT_PUBLIC_API_BASE_URL` regression (fixed 2026-08-27)

The first browser test of the deployed app failed every API call:
`POST http://localhost:8000/auth/login` → 503, "Failed to fetch" on the
login page. `NEXT_PUBLIC_*` vars are inlined into the JS bundle **at build
time**; the bundle had been built with `frontend/.env.local` setting
`NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` (the right *local dev*
value), so every visitor's browser called *its own* localhost instead of
a same-origin path. `app.yaml` env can't fix an already-inlined literal.
Fixed in three layers so it can't come back: (1) committed
`frontend/.env.production` = `same-origin` (and `.env.development` =
`localhost:8000`; the uncommitted `.env.local` that overrode both was
deleted); (2) `deploy-combined/build.sh` passes `same-origin` inline and
greps the output for `localhost:8000`, failing the build if found; (3)
`frontend/src/lib/api.ts` falls back to same-origin at runtime whenever
it's in a browser on a non-`localhost` host. Sanity check for any future
build: `grep -r localhost:8000 deploy-combined/.next/static` returns
nothing.

### 8b.6 Verification status

Verified in a real browser 2026-08-27: `POST /auth/login` returns 200
same-origin (no more `localhost:8000`), `/health` reports the DB
connected, login as `alice` works, Master Data Search does live fuzzy
matching, the relationship graph renders, and the Concierge agent chat
answers end-to-end (Concierge → Master Data → Search → live Anthropic API
→ live Lakebase) with clickable `[Name](record:ID)` links.

---

## 9. Master Data Requests (the approval workflow)

**Route:** `/mdm/requests` (the Review Queue) · **Endpoints:** `GET
/requests`, `GET /requests/{id}`, `POST /requests/{id}/approve`, `POST
/requests/{id}/reject`

This is the product's **first write path**, and the one place the "AI
drafts, a deterministic step decides" principle is enforced against real
state changes, not just narrative text.

### 9.1 The hard rule

**No agent, anywhere, can write to `master_records`.** The Party Request
Agent (§8.9) can only create a `pending` row. The only code that can turn
a pending row into an actual `master_records` change is
`approve_request()` in `backend/app/requests.py` — plain deterministic
Python, containing zero LLM calls, reachable **only** from `POST
/requests/{id}/approve`, which only the Review Queue UI's Approve button
calls.

### 9.2 What "Approval Tracking" actually is

There is **no Approval Tracking Agent**. `check_request_status` (§8.9) is
a read-only lookup tool, not an agent — it can report status
conversationally but cannot change it. The actual status transition
(`pending` → `approved`/`rejected` → `published`) is 100% deterministic
code, gated entirely behind direct human action on the Review Queue
screen.

### 9.3 Required-fields policy

- **Create:** `name` and `country` are required — `submit_request` raises
  a `RequestValidationError` otherwise (not just an instruction, an
  enforced check).
- **`lei`, if given:** checked against every existing active
  (non-deleted) record. An exact LEI match is treated as decisive — the
  request is **rejected outright** (not just flagged), since a matching
  LEI means this is provably the same legal entity, unlike name
  similarity which is only ever probabilistic.
- Checked at **both** submit time (fail fast) and approve time (the
  check that actually matters — two different pending requests can both
  propose the same new LEI before either is approved; approve time is
  the real write, so it's re-checked there, with a final
  `IntegrityError` catch as a backstop against that exact race).
- On approval, `lei` maps to `master_records.external_id` — the same
  column GLEIF ingestion populates, and the one with an actual database
  `unique` constraint. It's never left sitting inertly inside the JSON
  `attributes` blob.

### 9.4 Soft delete

A 'delete' request, on approval, sets `master_records.deleted_at` — the
row is **never hard-deleted**. A real `DELETE` would orphan
`relationship_edges` rows, any generated embeddings, and anything else
referencing that id;
soft-delete is also the correct default for data someone might need to
audit later. `search.py` and `compare.py` both filter out
`deleted_at IS NOT NULL` records.

### 9.5 Full walkthrough (real, executed end to end)

1. **Submit** (via chat, §8.9's create example) → `master_data_requests`
   row, `status = "pending"`, `audit_log` gets a `"submitted"` entry.
2. **Review** — `/mdm/requests` lists it: domain badge, type (Create),
   the proposed name, status pill, submitted timestamp, Approve/Reject
   buttons.
3. **Approve** → `POST /requests/27/approve` → `approve_request()`
   extracts `name`/`lei` from `proposed_attributes`, builds a new
   `MasterRecord`, `session.flush()`s it (Postgres auto-assigns `id` —
   see §9.6), sets the request's `status = "published"`, writes two
   `audit_log` entries (`"approved"` then `"published"`).
4. **Verified real:** `GET /search?q=Quorvath` returned "Quorvath
   Dynamics" as an **Exact** match, id `3399233` — a genuinely new,
   searchable record, indistinguishable from a GLEIF-sourced one to the
   rest of the app.
5. **Reject path, verified separately:** a second create request
   ("Zylophonic Testing Corp") was rejected instead — `GET
/search?q=Zylophonic` confirmed it **never appeared anywhere**;
   `master_records` was never touched.
6. **Update, verified real:** approving request #28 (Quorvath Dynamics'
   city → Boulder) — `SELECT attributes->>'city' FROM master_records
WHERE id = 3399233` returned `Boulder` afterward.
7. **Delete, verified real:** approving request #29 —
   `master_records.deleted_at` got set, and the record **disappeared
   from search results** entirely, replaced by legitimate unrelated fuzzy
   matches.

### 9.6 How a new record's `id` gets assigned

Nothing in application code assigns it. `master_records.id` is a
standard Postgres `SERIAL` primary key backed by the
`master_records_id_seq` sequence — the exact same sequence the original
3.4M-row GLEIF bulk load has been incrementing since. `MasterRecord(...)`
never sets `.id`; on `session.flush()`, SQLAlchemy issues an `INSERT ...
RETURNING master_records.id`, Postgres hands back the next sequence
value, and that's written into `record.id` in memory. No separate
ID-space for user-created vs. GLEIF-sourced rows — one sequence, one
table, guaranteed unique, never reused.

### 9.7 Cost-effectiveness note (live open question, not yet decided)

Approving/rejecting via the Review Queue is **always free** — zero LLM
calls. But checking status **conversationally** ("what's the status of my
request") costs **3 sequential LLM calls** (Concierge → Master Data →
Party Request Agent) to reach what's a single free `GET
/requests/{id}` on the Review Queue page. Discussed, not resolved: leave
as-is (a convenience worth the cost), drop the `check_request_status`
tool entirely and just point users to the Review Queue, or add a
pattern-matched bypass at the API layer for obviously-deterministic
phrasings. **Current decision: leave it as-is.**

---

## 10. Database Schema (complete, as of this snapshot)

**`master_records`** — the golden record table
| Column | Type | Notes |
|---|---|---|
| `id` | int, PK, autoincrement | See §9.6 |
| `domain` | varchar(50), indexed | Currently always `"Party"` |
| `name` | varchar(255), indexed | |
| `external_id` | varchar(20), unique, indexed, nullable | LEI for GLEIF records; also the field `lei` maps to on Party Request create/update |
| `attributes` | JSON | Everything else — country, city, legal_form, status, source, etc. |
| `embedding` | vector(384), nullable | Lazy — null until first search/compare touch |
| `name_tsv` | tsvector, generated | `GENERATED ALWAYS AS (to_tsvector('simple', name)) STORED` — DB-computed, `Computed()` in the ORM (see §12's bug note) |
| `created_at` | timestamptz | |
| `deleted_at` | timestamptz, nullable | Soft-delete marker (§9.4) |

**`word_frequencies`** — corpus statistics for search rarity-weighting
(`word` PK, `document_count`)

**`master_data_requests`** — pending/decided create/update/delete proposals
| Column | Type | Notes |
|---|---|---|
| `id` | int, PK | |
| `domain` | varchar(50), indexed | |
| `request_type` | varchar(20) | `create` \| `update` \| `delete` |
| `target_record_id` | int, nullable | Null for create; required for update/delete |
| `proposed_attributes` | JSON, nullable | Null for delete |
| `status` | varchar(20), indexed | `pending` \| `approved` \| `rejected` \| `published` — approval and publish happen atomically in this build, see §9.5 step 3 |
| `decision_note` | text, nullable | |
| `submitted_at` | timestamptz | |
| `decided_at` | timestamptz, nullable | |
| `submitted_by_id` | int, FK → `users.id`, nullable | Added with auth, §8a — nullable so a future non-chat submission path isn't precluded |
| `decided_by_id` | int, FK → `users.id`, nullable | Separate FK from `submitted_by_id` — submitter and decider are commonly different people, that's the point of the Review Queue |

**`audit_log`** — append-only trail, separate from `MasterDataRequest.status`
(`id` int, PK, `entity_type` varchar(50), `entity_id` int, `action`
varchar(50) — `submitted`/`approved`/`rejected`/`published`, `detail`
text nullable, `created_at` timestamptz)

**`users`** (added with auth, §8a) — `id` int PK, `username` varchar(50)
unique/indexed, `display_name` varchar(100), `role` varchar(50) nullable
(display label only, not RBAC), `password_hash` varchar(200) (PBKDF2, see
§8a), `created_at` timestamptz.

**`user_sessions`** (added with auth, §8a) — `token` varchar(64) PK
(opaque bearer token, not a JWT), `user_id` int FK → `users.id`,
`created_at` / `expires_at` timestamptz (12-hour TTL).

**`relationship_edges`** (replaces Neo4j, §3a/§7) — a directed ownership
edge between two `master_records` rows (parent owns child). `id` int PK,
`parent_id`/`child_id` int FK → `master_records.id` (both indexed, unique
together), `is_direct_parent`/`is_ultimate_parent` boolean,
`created_at` timestamptz. A parent/child pair can be both the direct
*and* ultimate parent at once (common with only one ownership level), so
both are flags on the same edge rather than separate rows. Walked via the
BFS in `app/graph.py` (§7), not Cypher — Neo4j is no longer part of this
stack at all.

---

## 11. Full API Reference

| Method | Path                              | Purpose                                                    | Auth |
| ------ | --------------------------------- | ---------------------------------------------------------- | ---- |
| GET    | `/health`                         | DB connectivity check                                      | No |
| POST   | `/auth/login`                     | `{username, password}` → `{token, user}`, §8a              | No |
| POST   | `/auth/logout`                    | Revokes the current session server-side, §8a               | Yes |
| GET    | `/auth/me`                        | Current logged-in user, for session restore on page load   | Yes |
| GET    | `/domains`                        | Distinct domain values actually present (not a fixed enum) | Yes |
| GET    | `/search?q=&domain=`              | Fuzzy search, §5                                           | Yes |
| GET    | `/master-records/{id}`            | Single record's full detail (backs the record modal, §8a)  | Yes |
| GET    | `/compare?ids=&ids=`              | Deterministic compare, §6a                                 | Yes |
| GET    | `/compare/summary?ids=&ids=`      | AI narrative over compare, §6b                             | Yes |
| POST   | `/concierge/chat`                 | `{prompt, history, graph_context?}` → the agent hierarchy, §8/§8.11 | Yes |
| GET    | `/requests?status=`               | List requests (Review Queue), §9                           | Yes |
| GET    | `/requests/{id}`                  | Single request detail                                      | Yes |
| POST   | `/requests/{id}/approve`          | `{decision_note}` → applies to `master_records`, §9.1      | Yes |
| POST   | `/requests/{id}/reject`           | `{decision_note}` → no data change                         | Yes |
| GET    | `/graph/{record_id}?hops=&limit=` | Relationship graph, §7                                     | Yes |

**Auth header — not `Authorization`.** Every "Yes" row above reads a
custom **`X-Relsun-Token`** header, not the standard `Authorization`
header — see §8a for why (Databricks Apps' gateway reserves
`Authorization` for its own OAuth validation and strips it before this
app ever sees the request). Any curl/script call must set
`X-Relsun-Token: <token from /auth/login>`.

All error responses use FastAPI's standard `{"detail": "..."}` shape.
Notable status codes: `401` = missing/invalid/expired session token,
`503` = agent not configured (no `ANTHROPIC_API_KEY`), `502` = agent call
failed, `409` = request already decided / not found (state conflict),
`400` = validation error (missing required field, duplicate LEI).

---

## 12. What's NOT Built Yet (be precise about this)

- **Data Catalog, Data Governance, Data Quality** — fully designed in
  `AGENT_INVENTORY.md` (dictionary/ontology/lineage agents,
  policy/standard/issue agents, quality-check/issue agents — ~30 agents
  total across the three modules), zero code. Sidebar placeholders only.
- **Item and Location domains** — no schema, no data, no agents. Only
  Party is real. (Explicit decision: design later, don't fabricate data
  now.)
- **The Recommendation Agent, full vision** — §8.10's first slice (built
  2026-08-20) covers real web search only for firmographic facts (HQ
  address, legal name), always as an unverified suggestion. Still **not**
  built: the internal-graph lookup ("memory before Google," §1), D&B, and
  the graph-aware, sales-acceleration flow itself ("this prospect
  connects to an existing customer via an ownership chain") described in
  the founders' original vision. Explicitly **not** the same thing as
  Compare Agent's name-similarity verdict — conflating the two was a real
  mistake caught mid-build (see the pivot addendum).
- **RBAC** — real login exists now (§8a, built 2026-08-14), but `role` is
  a display label only. Every logged-in user can approve/reject any
  request; there's no concept of "assigned approver" yet, by explicit
  decision (RBAC enforcement is future work, not designed).
- **The graph → action loop** ("act on this relationship" from a graph
  node) — explicitly deferred per direct instruction in favor of the
  graph interaction polish + Graph Context sub-agent pass (§7a/§8.11),
  pending a realistically-sized `existing_customer` flag set.
- **Real email notifications** — a pending request showing up in the
  Review Queue _is_ the notification. No email provider configured, no
  `notification_task` table.
- **Real downstream MCP propagation** — the "downstream" step in
  `approve_request()` only ever writes to `master_records` locally.
  Nothing propagates to any external system (there isn't one connected).
- **Scheduling** — every request today is approved via a manual click.
  No scheduler (e.g. a 9am daily downstream-publish job) exists.
- **Persistent, server-side per-agent memory/learning** — conversation
  continuity today is client-held history resent each turn (§8.3), not
  server-side persisted memory an agent could learn from over time.
  Explicitly flagged as an open design question, not solved.

### Real bugs found by testing (worth knowing about)

1. **`name_tsv` insert bug.** `MasterRecord.name_tsv` (a Postgres
   `GENERATED ALWAYS` column) was originally declared with
   `insert_default=None`, which forced an explicit `NULL` into every ORM
   `INSERT` — Postgres rejects that for a generated column. Never hit
   before because GLEIF ingestion uses raw SQL, not the ORM;
   `approve_request()`'s create path was the _first_ ORM-level insert in
   the whole codebase, and the first real pytest run against it caught it
   immediately. Fixed via SQLAlchemy's `Computed()`.
2. **React Strict Mode double-fire.** The Concierge page's
   auto-send-a-prefilled-prompt effect (for Search's "Create as new
   Party record" deep link) fired twice per page load in dev — Strict
   Mode double-invokes effects — submitting two identical create requests
   from one click. Fixed with a `useRef` guard.
3. **Pronoun resolution.** The Concierge's first-draft instructions
   didn't explicitly say to check conversation history before asking for
   clarification, so "compare it with X" as a follow-up failed until that
   was added explicitly (§8.4).
4. **LLM router self-rejection (2026-08-26, §8.11).** The Concierge's
   top-level call silently refused to hand off graph questions to
   `master_data` even after every piece of graph-context plumbing was
   wired and verified correct — a capability mentioned as one clause
   inside a longer instruction sentence isn't enough for a router to
   actually act on it with confidence. Fixed with a separate, imperative,
   "always hand off, that determination isn't yours to make" paragraph.
   Also worth remembering: the first attempt to verify this fix live
   looked like a regression because the browser's chat drawer was showing
   a stale, pre-fix answer from `sessionStorage` — a backend logic fix
   doesn't invalidate already-cached client-side chat history, so
   verifying in the UI means sending a genuinely new message, not reading
   an old one.

1, 2, and 4 were all caught only by actually running the system (tests /
clicking through the UI / a live chat message), not by reading the code —
worth remembering as a pattern for whatever gets built next.

---

## 13. Where to Look for More

- `CLAUDE.md` — the living, continuously-updated project reference.
  **This is the one to trust if it conflicts with this handbook.**
- `CONFIGURABLE_WORKFLOWS_AGENTS.md` — the commercial positioning
  (configurable-per-customer platform, not a fixed product) plus the full
  Agent Architecture Pivot addendum with build-sequence history.
- `AGENT_INVENTORY.md` — the complete planned agent tree across all four
  modules, including everything unbuilt.
- `DATA_STRATEGY.md` — the full data-loading philosophy and what's
  actually been executed vs. deferred (SEC EDGAR, UK Companies House).
- `deploy-combined/DEPLOY.md` — Databricks Apps hosting in full: the
  one-app architecture, `build.sh`, the exact sync/deploy commands, and
  the two deploy-pipeline traps (see also §8b).
- `Relsun_Initial slides.pdf` — the founders' original wireframe deck.
