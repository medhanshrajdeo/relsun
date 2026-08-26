# Relsun — Data Strategy

This document extends CLAUDE.md and CONFIGURABLE_WORKFLOWS_AGENTS.md. It
covers what data Relsun's local build is seeded with, why, and how it's
ingested. Read this before writing any data-loading code.

> **Platform note (2026-08-24):** every "Neo4j" reference below is
> superseded — see CLAUDE.md's "Platform pivot" section. The relationship
> graph now lives as a `relationship_edges` table in the same Databricks
> Lakebase (Postgres-wire-compatible) instance as `master_records`, not a
> separate graph database. Left as-is here rather than rewritten, per this
> repo's convention of preserving decision history inline (see the Agent
> Architecture Pivot addendum in `CONFIGURABLE_WORKFLOWS_AGENTS.md` for the
> precedent) — the ingestion *sequence* and *intent* described below are
> still accurate, only the target database changed.

---

## 1. The governing principle

**Raw data: load broadly and really, with no artificial narrowing.
Expensive processing (embeddings, LLM calls): scoped narrowly, generated
on demand, not pre-computed for everything.**

Earlier planning considered hand-picking a single seed company's
subsidiary tree to keep the build simple. That approach was explicitly
rejected — the founders do not want the product or its data to feel
artificially limited, even at the demo stage. The correct way to satisfy
"real, broad, unrestricted data" without an unmanageable build is to
recognize that the two things people usually conflate — data volume and
processing cost — are not actually coupled. Loading millions of rows into
Postgres/Neo4j is cheap and fast. Generating a vector embedding or calling
an LLM for each of those rows is what's actually expensive. So: load
everything real that's available; only generate embeddings/run agents
against records that are actually being searched/used.

---

## 2. Why NOT synthetic/fabricated relationship data

The product's flagship feature (Relationship Intelligence) only has real
sales/credibility value if the ownership chains it surfaces are true and
verifiable. A demo built on invented relationships proves nothing to a
skeptical data-team evaluator and creates real risk if anyone fact-checks
it. All entity and relationship data must come from real, open, legally
usable sources. The ONE thing that is legitimately "invented" is Relsun's
own product metadata layered on top of real entities — specifically, a
`relationship_status` field (e.g., `existing_customer`) marking which real
companies are, for demo purposes, treated as already being Relsun's own
customers. This is not fabricated relationship/ownership data — it is
exactly the kind of status flag any real Relsun deployment would store
about its own real customers. It sits alongside real data, it does not
replace or distort it.

---

## 3. Primary data source: GLEIF (Global Legal Entity Identifier Foundation)

**What it is:** A global regulatory body maintaining the LEI (Legal Entity
Identifier) system. Provides free, open, regulator-grade corporate entity
and ownership-relationship data — the closest free equivalent to D&B's
paid Corporate Linkage product.

**Scale (current, as of mid-2026):**
- Level 1 data ("who is who" — entity reference data: name, registered
  address, HQ address, legal form, status): ~3.3 million records, ~490MB
  as a full concatenated file
- Level 2 data ("who owns whom" — direct parent + ultimate parent
  relationship records): ~658,000 records, ~35MB
- Updated three times daily via "Golden Copy" files, or bi-weekly via
  simpler "Concatenated Files"
- Underlying format is LEI-CDF (Common Data Format), XML-based; also
  available as CSV via the Concatenated/Golden Copy files
- Free, no registration or API key required, no usage restriction for
  this kind of use

**Known limitation (do not build promises around this without checking
real data first):** LEI/relationship reporting skews toward larger,
regulated, or financial-market-facing entities. Not every real-world
subsidiary or PE-portfolio relationship will be present — GLEIF's Level 2
data specifically reports "accounting consolidating parent" relationships,
which is a different concept from private-equity fund ownership. GLEIF
itself states not all entities report parent relationships even when they
exist. Do not assume any specific relationship (e.g., a PE-portfolio
chain) will be present — verify with real queries before building a demo
narrative around a specific example.

### 3a. Ingestion approach: bulk file, not the live API

For the initial full load, use the **bulk Concatenated File download**
(Level 1 + Level 2), not the live GLEIF API. The bulk files are free,
direct downloads (CSV or XML), and are the right tool for a one-time full
ingestion into Postgres/Neo4j. This satisfies "load the real, complete
open dataset, no artificial narrowing at the data layer."

The **GLEIF API** (also free, no API key, no registration) becomes
relevant LATER for:
- Live lookups of entities NOT already in the bulk-loaded data (i.e., the
  D&B-equivalent "check external sources for entities not yet in our
  system" enrichment flow from CLAUDE.md's Relationship Intelligence
  section)
- Targeted "children" queries (given a parent LEI, find who reports it as
  their parent) — useful for later, deeper exploration beyond what the
  bulk Level 2 file already contains

### 3b. Ingestion pipeline (what to actually build)

1. Download the GLEIF Level 1 Concatenated File (entity records) and
   Level 2 Concatenated File (relationship records)
2. Parse both (CSV recommended over XML for simpler parsing at this
   volume)
3. Load Level 1 records into Postgres as master/golden records — map
   GLEIF fields to Relsun's domain model (LEI → internal entity ID, legal
   name → Entity Name, registered/HQ address → address fields, entity
   category → a reasonable mapping toward Party/Account/Supplier domain
   tagging — exact domain-mapping logic is an implementation decision to
   work out at build time, not fully prescribed here)
4. Load Level 2 records into Neo4j as relationship edges (child LEI →
   parent LEI, child LEI → ultimate parent LEI), referencing the same
   entity IDs used in Postgres
5. Do NOT generate vector embeddings during this load step — that happens
   lazily, per Section 1 and per CLAUDE.md Phase 2
6. After loading, apply the `relationship_status` demo flag (Section 2)
   to a small, deliberately chosen handful of real loaded entities to mark
   them as "existing Relsun customers" for demo purposes

---

## 4. Secondary/complementary source: SEC EDGAR (Exhibit 21 filings)

**What it is:** US public companies are legally required to file a
complete list of all subsidiaries as "Exhibit 21" of their annual 10-K
report, via SEC EDGAR (free, public, no API key required for basic
access).

**Why it matters:** this is a legal disclosure requirement, not a
voluntary report — so for any US public company, Exhibit 21 gives a
complete, authoritative subsidiary list even where GLEIF's voluntary
Level 2 reporting might be incomplete for that company. Useful as a
cross-reference/validation source, and as a fallback discovery method for
specific companies of interest where GLEIF's relationship data looks thin.

**Status:** not required for the initial full GLEIF bulk load (Section 3),
since that load is comprehensive on its own. Keep EDGAR in reserve for
validating or filling gaps around specific companies chosen for demo
narratives, or for deeper "known conglomerate" exploration later.

---

## 5. Deferred sources (explicitly NOT part of this build phase)

- **OpenStreetMap (Overpass API)** — real, free, global retail/franchise
  location data (name, address, coordinates, hours, phone). Deferred
  because the Location domain itself is deferred — the first build proves
  the Relationship Intelligence loop using Party/Account/Supplier-type
  entities from GLEIF, not Location data. Revisit once Location domain
  work begins.
- **UK Companies House (PSC register)** — free, bulk-downloadable
  beneficial-ownership/significant-control data, UK entities only. More
  conceptually aligned with PE-style ownership than GLEIF's Level 2 data.
  Deferred — not needed for the first demo narrative, which does not
  require the relationship to specifically be PE ownership (any real,
  verifiable ownership connection satisfies the demo's purpose). Revisit
  if/when a demo specifically needs a PE-portfolio-style example.
- **D&B API** — the originally planned paid enrichment source for
  entities not in the local system. Still the long-term plan for live,
  real-time enrichment (per CLAUDE.md's Relationship Intelligence
  section) — not needed for the initial bulk data load, since GLEIF
  already provides a large, free, real base dataset to build and demo
  against before any paid data contract is necessary.

---

## 6. What "successful data" looks like for this build

- The full open GLEIF dataset (Level 1 + Level 2) is loaded into Postgres
  + Neo4j — real, complete, not artificially narrowed
- A small number of real, loaded entities are flagged as
  `existing_customer` for demo purposes — this is Relsun's own product
  metadata, not fabricated external data
- Embeddings exist only for records that have actually been searched/
  touched, not pre-generated for the full 3.3M entity set
- The relationship graph in Neo4j reflects GLEIF's real, verified
  parent/subsidiary data — any "wow, these are connected" moment in a
  demo is backed by real, checkable data, not invented for the occasion

---

## 7. What the first demo must prove (ties data strategy to the product)

The demo is not "search works" or "the graph renders." It's the full
loop:

1. Search for a company (real, from the loaded GLEIF data, or an
   unrelated-looking one)
2. Open its relationship graph — see its real ownership chain
3. Discover that chain leads back to an entity flagged
   `existing_customer`
4. **Act on that discovery** — trigger the "act on this relationship"
   action from the graph view
5. Confirm a real Master Data Request was created as a result, visible in
   the Master Data Requests screen, entering the approval workflow

Steps 1-3 prove the Relationship Intelligence differentiator. Steps 4-5
prove the "graph drives action, not just insight" differentiator, and
the "centralized/operational MDM" positioning from CLAUDE.md. A build
that only accomplishes steps 1-3 is an incomplete first demo — build
toward the full loop, not just the visually impressive part.

---

## Addendum: what actually happened at build time (2026-08-11/12)

- Bulk ingestion was built against GLEIF's **XML** concatenated files
  (Level 1 = LEI-CDF v3.1, Level 2 = RR-CDF v2.1), not CSV as this
  document originally recommended — confirmed at build time that CSV
  wasn't actually offered for the current concatenated-file bulk
  download, and the user explicitly confirmed keeping XML rather than
  reshaping the pipeline around a converted/alternate format.
- Actual loaded scale: ~3.4M entities, ~169K active ownership edges
  (`IS_DIRECTLY_CONSOLIDATED_BY` / `IS_ULTIMATELY_CONSOLIDATED_BY`,
  `RelationshipStatus == ACTIVE` only). **Updated 2026-08-25:** the
  Databricks Lakebase migration (see the Platform note at the top of this
  file) reloaded all data from the same source GLEIF ZIPs — no
  re-download, same pipeline — and the edge count that came back was
  ~257K, not ~169K. Left as a separate note rather than edited in place,
  per this file's own convention above; not a new dataset or a changed
  filter, just a different actual count on reload.
- All bulk-loaded GLEIF entities were mapped to a single `domain =
  "Party"` rather than split across Party/Account/Supplier — GLEIF itself
  has no customer/supplier concept, and inventing one would conflict with
  Section 2's "don't fabricate" principle. Relsun's own
  `relationship_status` metadata layer (Section 2) is what actually
  distinguishes an `existing_customer` from any other `Party`, not GLEIF's
  data. This also drove a related decision: the domain taxonomy is **not**
  a hardcoded enum anywhere in the codebase (backend `domain` is a plain
  string column, frontend `Domain` type is a plain string with dynamic
  `GET /domains` discovery), specifically so a future customer's own data
  — which may have a completely different domain shape — isn't forced
  into GLEIF's.
- Embeddings remained fully lazy as specified (`ensure_embeddings()`,
  generated only for records actually touched by a search/compare call).
- Steps 1-3 of the Section 7 demo loop (search → graph → discover
  `existing_customer` in the chain) are built and verified working.
  Steps 4-5 (act on the relationship → real Master Data Request created)
  are **not built** — the graph UI has a disabled "Act on this
  relationship" button as a placeholder. Master Data Requests is
  unstarted. Don't describe the full demo loop as complete.
