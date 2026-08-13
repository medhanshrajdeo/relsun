# Relsun — Project Reference

> **Note on this document:** no `CLAUDE.md` existed anywhere in this repo's
> git history before this was written (2026-08-12) — confirmed via
> `git log --all --full-history`. Earlier sessions clearly worked from one
> (see references to "CLAUDE.md's Relationship Intelligence section" etc. in
> `.claude/projects/C--Relsun/memory/`), but it was never actually committed
> here, so it's reconstructed from: the founders' wireframe deck
> (`Relsun_Initial slides.pdf`, repo root), auto-memory notes from earlier
> sessions, the two addendum documents below, and this session's build
> decisions. Correct anything that's wrong or missing — this is the
>持续 source of truth going forward, so it's worth getting right.

## What Relsun is

An AI-native Master Data Management (MDM) platform. Not just a system of
record — the differentiator is that discovering a relationship in the data
(e.g. a prospect turns out to be owned by a parent that's also an existing
customer) actually **triggers a workflow** (a Master Data Request, an
approval chain), not just a passive visualization. "The graph drives
action, not just insight."

Product surface (per the founders' wireframe deck, `Relsun_Initial
slides.pdf`):
- **Data Concierge** — an AI chat/voice interface, home screen ("How can we
  help you today?")
- **Data Catalog** — Data Dictionary, Data Ontology, Data Lineage, Change
  Requests
- **Data Governance** — Data Policies, Data Standards, Change Requests,
  Issue Management
- **Data Quality** — Data Quality Checks, Change Requests, Issue Management
- **Master Data Management** — Master Data Search, Master Data Requests
- **My Account**

Only **Master Data Management** (Search, Compare, View Graph) is built so
far. Data Catalog / Governance / Quality / My Account are present in the
sidebar as "Soon" placeholders, matching the wireframe's full nav, but have
no implementation behind them yet.

## Relationship Intelligence (the flagship feature)

Three concrete use cases, not just "prospect → existing customer":

1. **Sales acceleration** (the one the founders keep repeating): a prospect
   is owned by a parent/PE firm that also owns an existing customer — surface
   that chain so a rep can use the warm relationship instead of cold
   outreach. Recurring illustrative example: Hanger (prospect) → owned by
   Patient Square (a PE firm) → Patient Square also connected to Boeing
   (existing customer). This is a *hypothetical* narrative shape, not a real
   ownership fact — don't treat it as real-world data.
2. **Impact analysis** — e.g. closing a distribution location: show which
   customers/suppliers are downstream of it before acting.
3. **Supplier consolidation** — a new supplier's parent turns out to already
   sell to us through a *different* existing supplier relationship, revealing
   negotiation leverage.

**Lookup design principle ("memory vs. Google"):** check the internal graph
first; only fall back to live web search (+ D&B, eventually) when an entity
isn't already known — like a person recognizing someone they know instantly
vs. having to look a stranger up.

**Graph rendering decision (2026-08-12):** custom SVG + d3-force, not an
embedded Neo4j Bloom. Bloom requires a paid Enterprise/Aura tier ($1,200–
$2,500/user/year) and — more importantly — can't host the "act on this
relationship" action the product actually needs (no way to inject a
custom "create Master Data Request" button into a closed third-party graph
tool). Same "thin wrapper" trap the Configurable Workflows addendum warns
about, just applied to Neo4j instead of Foundry.

## Master Data Search

Fuzzy/typo-tolerant search, not just exact match. Canonical wireframe
example: searching "Hanger" should also surface "Hangr" and "Hangry" as
similarity matches.

**Design (`backend/app/search.py`):** blocking (cheap, recall-oriented,
Postgres pg_trgm + pgvector) → composite scoring (Jaro-Winkler, trigram,
vector cosine similarity, phonetic/metaphone) → threshold. Explicitly
**not** vector-embeddings-alone — that was tried first and missed
typo-style matches ("Boeng" didn't surface "The Boeing Company" in the top
5 nearest neighbors; MiniLM-style embeddings capture conceptual similarity,
not character-level edit distance).

At bulk scale (3.4M real rows, see Data Strategy below) this needed several
follow-up fixes: determinism (missing `ORDER BY`), performance (index-
accelerated `pg_trgm` operators instead of the bare `word_similarity()`
function), and relevance (rarity-weighted scoring computed from real corpus
statistics via Postgres's `ts_stat()`, not a hardcoded stopword list, plus
tiered ranking for the "Exact" bucket so a coincidental substring match like
"nike" inside "kliniken" can't crowd out the real "Nike" entities).

## Configurable Workflows & Agents (commercial positioning)

Full text preserved verbatim in [`CONFIGURABLE_WORKFLOWS_AGENTS.md`](./CONFIGURABLE_WORKFLOWS_AGENTS.md),
including the 2026-08-12 **Agent Architecture Pivot** addendum at the
bottom of that file (this section already reflects the pivot; the doc's
earlier sections are marked superseded inline rather than rewritten, to
preserve decision history). The full planned agent hierarchy across all
four modules is transcribed in [`AGENT_INVENTORY.md`](./AGENT_INVENTORY.md)
from the founders' `Relsun_Agents_Inventory.xlsx`.

Summary: Relsun is a **platform with opinionated defaults**, not a fixed
product — a technical customer's developer can reshape approval chains,
matching thresholds, and agent instructions; a non-technical customer just
gets the sane defaults. Explicit anti-pattern to avoid: becoming a thin UI
skin over Microsoft Foundry (or any agent platform) — defensibility has to
come from MDM-specific domain logic, the relationship graph, and a
purpose-fit config UI, not the wrapped tool itself.

**Design principle (unchanged by the pivot):** AI agents *draft*, a
separate deterministic step *decides what gets written*. An agent can
propose a comparison summary or a relationship suggestion, but never
silently mutate governed master data.

**Architecture (pivoted 2026-08-12): a hierarchy of agents that call each
other as tools, not a fixed visual workflow sequence.** The earlier idea
of a drag-and-drop Trigger → Logic → Action → AI workflow canvas (Attio-
style) is dropped — agentic systems shouldn't be authored as a rigid
step-1-then-step-2 chain. Instead: a Concierge Agent sits on top, routing
by domain to module agents (Master Data, and eventually Catalog/
Governance/Quality), which route by intent to task agents (Search,
Compare, Request), which route to domain-specific sub-agents (Party,
Item, Location), which call their own sub-agents (insert/update,
recommendation, approval-tracking, downstream) as needed — 4-5 layers
deep, per `AGENT_INVENTORY.md`. Each agent decides at runtime, from its
own plain-English instructions, which tool or sub-agent a given prompt
calls for; nothing is a hardcoded sequence. Triggers are prompts in all
cases — typed by a user, generated by a UI action (e.g. clicking
"Approve"), or generated on a schedule (e.g. a 9am daily downstream-
publish run) — so the hierarchy itself doesn't need to know which kind
of trigger started it. Customer configuration = editing an agent's
plain-English instructions (still no-code), not building a flow diagram.

**Technical decision (revised 2026-08-12):** Foundry is now a **UX/
architecture reference only** — its portal's "an agent's tools can
include other agents" concept is what the hierarchy above is modeled on,
and its visual layout (master agent, sub-agent boxes) is the direct
design inspiration for how Relsun should present its own agent hierarchy.
It is **not a runtime dependency**: agents are built in plain Python,
calling an LLM API directly (provider not yet chosen), not Foundry Hosted
Agents / `azure-ai-agents`. `backend/app/agents/compare_summary.py` still
uses the old Foundry SDK approach and is the first thing to rewrite under
the new pattern — see the pivot addendum for the full sequencing.
Immediate build priority is the **Master Data** agent branch only
(Party now, Item/Location designed-but-data-deferred); Catalog/
Governance/Quality stay documented-not-built, matching their "Soon"
sidebar placeholders.

## Data Strategy

Full text preserved verbatim in [`DATA_STRATEGY.md`](./DATA_STRATEGY.md).

Summary: **raw data loads broadly and really, no artificial narrowing;
expensive processing (embeddings, agent calls) is scoped narrowly and
generated on demand.** Volume and processing cost are decoupled — loading
millions of rows is cheap, generating a vector embedding or calling an LLM
per row is what's expensive. Concretely: bulk-load GLEIF's full Level 1
(entities) + Level 2 (ownership) concatenated files, no hand-picked subset;
never pre-compute embeddings for the whole set, only for records actually
touched by a search or compare. The only intentionally-fabricated data is
`relationship_status: existing_customer`, layered on top of real entities
as Relsun's own product metadata — not invented relationships.

Real, not synthetic, because the Relationship Intelligence pitch only has
sales/credibility value if the ownership chains are true and verifiable —
a demo built on invented relationships proves nothing to a skeptical data
team and creates real risk if fact-checked.

**Actually executed (2026-08-11/12):** ~3.4M real entities and ~169K real
ownership edges bulk-loaded from GLEIF (see the git log for the ingestion
pipeline — `app/gleif.py`, `scripts/ingest_gleif_*.py`). SEC EDGAR
(Exhibit 21) and UK Companies House are documented as reserve/deferred
sources in the Data Strategy doc, not yet built.

## Build sequence & current status

Original phase numbering (0–4) predates the two addenda above, which layer
a Stage 1/2/3 sequence on top for the configurable-workflows work
specifically. Both numbering schemes are referenced in git history /
memory; treat "Phase" as the MDM feature build-out and "Stage" as the
config-layer build-out layered on top of it.

| Phase | What | Status |
|---|---|---|
| 0 | Local dev environment (Docker Postgres+pgvector, Neo4j, FastAPI health check, Next.js scaffold) | ✅ Done |
| 1 | Seed data | ✅ Superseded — real GLEIF bulk load (3.4M entities, 169K edges) replaced the original hand-picked demo set entirely, per Data Strategy's explicit rejection of narrowed seed data |
| 2 | Master Data Search | ✅ Done — fuzzy matching, deterministic, fast, relevance-ranked (see fixes above) |
| 3 | Master Data Compare | ✅ Deterministic comparison (field diffs, pairwise duplicate verdicts) working and reachable from Search. ✅ AI summary agent (`compare_summary.py`) **verified working** as of the Compare Agent build below — first live caller confirmed it drafts correctly. |
| 4 | View Graph (Relationship Intelligence) | ✅ Done — custom SVG + d3-force visualization, verified end-to-end against real ownership data including the flagship "existing customer discovered in chain" narrative |
| — | Master Data Requests (approval workflow) | ✅ **Party domain done, built and live-verified 2026-08-13.** Full hierarchy: `POST /concierge/chat` → Concierge → Master Data → {Search, Compare, Request}, all on the live Anthropic API. Request flow: `party_request_agent.py` gathers create/update/delete details conversationally (resolving names to IDs via Search first when needed) and saves a pending proposal — it never applies anything itself. `app/requests.py` holds the only code in the repo allowed to write to `master_records` (`approve_request`/`reject_request`), called exclusively from `POST /requests/{id}/approve`\|`reject` when a human acts in the new Review Queue screen (`frontend/src/app/mdm/requests/page.tsx`, sidebar link now live). Live-verified end to end: create→approve produces a real, searchable record; create→reject never touches `master_records`; update/delete by name resolve correctly and apply/soft-delete correctly (soft-delete via `master_records.deleted_at`, excluded from search). **Required-fields policy** (added 2026-08-13, direct instruction): create requests must have `name` + `country` — `submit_request` rejects otherwise; `lei` is optional but, when given, is checked for an existing active record with the same value (an exact LEI match is decisive, unlike name similarity — rejected outright, not just flagged) and maps to `master_records.external_id` on approval, not left in the JSON `attributes` blob. Same LEI check applies to update. Checked at both submit time and again at approve time (the actual write), since two pending requests can both still be pending when one gets approved first — approve-time is the one that has to be airtight; a stray `IntegrityError` is the final backstop. **No Recommendation Agent** — deliberately deferred as its own graph-aware, sales-acceleration feature (see the pivot addendum), not folded into this pass as a name-similarity wrapper. Not done: Item/Location Request Agents (data-deferred), RBAC, real email, real downstream MCP propagation, scheduling. See `AGENT_INVENTORY.md` and the pivot addendum in `CONFIGURABLE_WORKFLOWS_AGENTS.md`. |
| — | Merge & survivorship | ⬜ Not started |
| — | Data Catalog / Governance / Quality agent hierarchies | ⬜ Fully designed in `AGENT_INVENTORY.md` (2026-08-12), not built — matches their current "Soon" sidebar placeholders. Do not start building these until the Master Data agent hierarchy is solid. |
| Stage 3 | Customer-facing config layer (now: editable agent instructions, not a visual workflow builder — see pivot addendum) | ⬜ Not started — explicitly out of scope until the Master Data agent hierarchy is solid |

**What to check before trusting the table above:** it's a snapshot, not
live state. Verify against actual code/git log before assuming something
listed as ✅ is still true, especially for anything touching external
services (Foundry, GLEIF's live API) that this repo doesn't control.

## Tech stack

- **Backend:** Python, FastAPI, SQLAlchemy, Postgres 16 + pgvector +
  pg_trgm (Docker), Neo4j 5 Community (Docker), Alembic migrations
- **Frontend:** Next.js (App Router), TypeScript, Tailwind CSS, lucide-react
  icons, d3-force (custom graph rendering, no charting/graph library)
- **Embeddings:** sentence-transformers `all-MiniLM-L6-v2`, local, lazy
  (never pre-computed in bulk)
- **AI agents:** custom Python, calling the **Anthropic API directly**
  (`anthropic` SDK — see `app/agents/framework.py`'s `Agent`/`Tool`/
  `agent_as_tool()`). Model is set via `ANTHROPIC_MODEL` in `.env`
  (`claude-sonnet-5` is `config.py`'s fallback default; local dev is
  currently running `claude-haiku-4-5-20251001` for cost-efficient
  verification — either is valid, this is a per-environment choice, not
  a fixed product decision). Foundry is a UX/architecture reference only
  as of 2026-08-12, not a runtime dependency. **Verified working
  2026-08-12** against the live API: `POST /concierge/chat` →
  Concierge → Master Data → Search, 4 real prompts confirmed correct.

## Quality bar

"Think like an entrepreneur. Everything being built should serve a purpose
to your idea and be as close to perfect as it can be." A terse phase
description is the floor, not the spec — think through what actually makes
a feature good (multiple matching signals, proper empty/loading states,
forward-compatible UI for not-yet-built phases with clear "coming later"
affordances rather than dead/missing buttons) before calling it done. It's
fine and encouraged to pause mid-phase and flag a real limitation found
during testing rather than silently shipping something mediocre — and
conversely, **don't claim something is "done" if it's only scaffolded and
never actually verified against a real dependency** (see the Compare AI
agent status above — this was gotten wrong once already this session).
