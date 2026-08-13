# Relsun — Agent Inventory

> Source: `Relsun_Agents_Inventory.xlsx` (repo root), transcribed 2026-08-12
> so it's diffable/versioned instead of living only in a binary spreadsheet.
> This is the **full planned agent hierarchy across all four product
> modules**, produced as part of the 2026-08-12 agent-architecture pivot
> (see the "Agent Architecture Pivot" addendum in
> [`CONFIGURABLE_WORKFLOWS_AGENTS.md`](./CONFIGURABLE_WORKFLOWS_AGENTS.md)
> for the *pattern* — this file is the concrete *inventory* of agents that
> pattern gets applied to).

**Build priority (confirmed 2026-08-12):** only the **Master Data** branch
below is being actively built next — it extends the Search/Compare/Graph
UI that already exists. Data Catalog, Data Governance, and Data Quality
are documented here as the full designed vision, matching their current
"Soon" sidebar placeholders — not built yet, not scheduled yet.

Every agent in this tree follows the same shape, per the pivot: Python
code with (a) plain-English, customer-editable instructions and (b) a set
of tools, where a tool can be a real function (DB read/write,
notification, graph query) *or another agent*. Nothing here is a fixed
step-1-then-step-2 sequence — which sub-agent (if any) gets called is a
runtime decision the calling agent makes from its own instructions and
the incoming prompt, not a hardcoded chain.

---

## Data Concierge Agent *(top-level orchestrator)*

Top-level orchestrator behind the Home concierge experience. Interprets a
user's text or voice query, resolves intent, and routes it to the
appropriate module agent (Catalog, Governance, Quality, or Master Data) —
returning a direct answer, a deep link, or a workflow hand-off.

---

## Data Catalog Agent *(module orchestrator — designed, not built)*

Module-level orchestrator for Data Catalog. Coordinates the dictionary,
ontology, lineage, and change-management sub-agents, and routes
catalog-scoped concierge queries or workflow triggers to the right one.

- **Data Dictionary Agent** — reads `glossary_term` records (definitions,
  contacts, technical metadata: system of record, table, column) and
  answers glossary search/definition queries for the Data Glossary screen
  and concierge lookups.
- **Data Ontology Agent** — manages term-to-term relationships in the
  ontology graph (Neo4j `:Term` nodes and labeled `:RELATED_TO` edges),
  and supports the Data Ontology screen's browse/search and
  relationship-type queries.
- **Data Lineage Agent** — reads `lineage_mapping` records (system, table,
  and column mappings per term) and traces a term/attribute's flow across
  source and target systems for the Data Lineage screen.
- **Data Catalog Change Agent** — orchestrates the Data Catalog Change
  Management workflow end to end, coordinating the three sub-agents below
  for a submitted glossary/ontology/lineage change request.
  - **Data Catalog Change Intake Agent** — captures a submitted catalog
    change request, validates required fields, and creates the
    `change_request` record that enters the Catalog Change Management
    queue.
  - **Data Catalog Change Recommendation Agent** — reviews a pending
    catalog `change_request` and generates a recommendation (approve,
    reject, or edit) for the human reviewer, informed by the object's
    existing associations and tags.
  - **Data Catalog Change Approval Tracking Agent** — tracks a catalog
    `change_request`'s status through review, and on approval applies the
    change to the underlying `glossary_term`, ontology relationship, or
    `lineage_mapping` and logs the update to `audit_log`. Commits the
    change once all needed approvals for the request are received.

---

## Data Governance Agent *(module orchestrator — designed, not built)*

Module-level orchestrator for Data Governance. Coordinates the policies,
standards, change-management, and issue sub-agents, and routes
governance-scoped concierge queries or workflow triggers to the right one.

- **Data Policies Agent** — reads `data_policy` records (description,
  tags, associations, validation query configuration) and runs/schedules
  validation queries to compute and update each policy's
  `compliance_score`.
- **Data Standards Agent** — reads `data_standard` records (description,
  tags, associations) and surfaces the Data Quality Rule(s) that
  operationalize each standard, since standards themselves carry no score.
- **Data Governance Change Agent** — orchestrates the Data Governance
  Change Management workflow, coordinating the three sub-agents below for
  a submitted policy or standard change request.
  - **Data Governance Change Intake Agent** — captures a submitted
    governance change request (policy or standard), validates required
    fields, and creates the `change_request` record that enters the
    Governance Change Management queue.
  - **Data Governance Change Recommendation Agent** — reviews a pending
    governance `change_request` and generates a recommendation (approve,
    reject, or edit) for the human reviewer, informed by the object's
    existing associations and tags.
  - **Data Governance Change Approval Tracking Agent** — tracks a
    governance `change_request`'s status through review, and on approval
    applies the change to the underlying `data_policy` or `data_standard`
    and logs the update to `audit_log`. Commits the change once all
    needed approvals for the request are received.
- **Data Governance Issue Agent** — orchestrates issue handling for
  governance compliance violations, opened when a policy's validation
  query returns a failing or below-threshold `compliance_score`,
  coordinating the two sub-agents below.
  - **Data Governance Issue Notification Agent** — notifies the relevant
    policy owner or governance lead when a compliance violation is
    opened, following the same `notification_task` pattern used for
    Master Data's Notify/Flag actions.
  - **Data Governance Issue Closure Agent** — tracks investigation and
    remediation of an open governance compliance issue through to
    resolution, and logs the closure and any resulting policy/score
    change to `audit_log`.

---

## Data Quality Agent *(module orchestrator — designed, not built)*

Module-level orchestrator for Data Quality. Coordinates the checks,
rule-change-management, and issue sub-agents, and routes quality-scoped
concierge queries or workflow triggers to the right one.

- **Data Quality Checks Agent** — executes each `quality_rule`'s
  validation query on its scheduled run, computing and updating
  `current_score` and `last_run_at`. *(One of the few agents that's
  schedule-triggered rather than prompt-triggered — see the trigger-types
  discussion in the architecture addendum.)*
- **Data Quality Rule Change Agent** — orchestrates the change-management
  workflow for `quality_rule` definitions themselves (new rule, modified
  logic, retirement), coordinating the three sub-agents below.
  - **Data Quality Rule Change Intake Agent** — captures a submitted
    quality rule change request, validates required fields, and creates
    the `change_request` record that enters the review queue.
  - **Data Quality Rule Change Recommendation Agent** — reviews a pending
    quality rule change request and generates a recommendation (approve,
    reject, or edit) for the human reviewer, informed by the rule's
    linked `data_standard` and current score history.
  - **Data Quality Rule Change Approval Tracking Agent** — tracks a
    quality rule `change_request`'s status through review, and on
    approval applies the change to the underlying `quality_rule` and logs
    the update to `audit_log`. Commits the change once all needed
    approvals for the request are received.
- **Data Quality Issue Agent** — orchestrates the Data Quality Remediation
  workflow: opens a `quality_issue` when a rule execution detects a
  violation, and coordinates the two sub-agents below.
  - **Data Quality Issue Notification Agent** — notifies the assigned
    data steward when a new `quality_issue` is opened or reassigned,
    following the same `notification_task` pattern used elsewhere in the
    platform.
  - **Data Quality Issue Closure Agent** — tracks investigation and
    remediation of an open `quality_issue` through to resolution, logging
    the closure to `audit_log` so the rule's next scheduled run reflects
    the fix.

---

## Master Data Handling Agent *(module orchestrator — 🎯 active build target)*

Module-level orchestrator for Master Data. Coordinates the search,
compare, and request sub-agents across all master data domains (Party,
Item, Location), and routes master-data-scoped concierge queries or
workflow triggers to the right one.

- **Master Data Search Agent** — powers the Master Data Search screen:
  looks up an entity internally first, and — if not found — triggers the
  AI web-search check to surface a plausible existing relationship (e.g.,
  an owning parent already in the system) before the user proceeds to
  Create. *(This is the "memory vs. Google" lookup principle already
  documented in CLAUDE.md's Relationship Intelligence section — this
  agent is the one that implements it.)*
- **Master Data Compare Agent** — evaluates a candidate master data record
  against existing entities and returns a duplicate-match, related-entity,
  or no-match outcome with a confidence score — the core logic behind the
  Create workflow's duplicate/relationship check step. *(The existing
  deterministic `compare.py` + the Compare summary agent are the current
  implementation of part of this; see the architecture addendum for how
  this gets re-platformed off Foundry.)*
- **Master Data Request Agent** — top-level orchestrator for all master
  data lifecycle requests (create, update, delete), routing each request
  to the appropriate domain-specific request agent below.
  - **Party Request Agent** — orchestrates the full create/update/delete
    lifecycle for Party-type master data (customers, suppliers, third
    parties), coordinating the four sub-agents below. *(The only domain
    with real data loaded today — GLEIF, 3.4M entities.)*
    - **Party Insert and Update Agent** — executes the insert or upsert of
      a Party record to `mastered_entity`.
    - **Party Action Recommendation Agent** — generates the recommendation
      shown to the user during a Party request — e.g., which action to
      take on a related-entity match, or the safe/caution/not-advisable
      guidance on a proposed update.
    - **Party Approval Tracking Agent** — tracks a Party
      `resolution_request`, `entity_update_request`, or
      `entity_deletion_request` through to resolution, including any
      resulting `notification_task` or `review_queue_item`.
    - **Party Downstream Agent** — propagates an approved Party change to
      downstream systems via MCP connections and records the `audit_log`
      entry. *(This is the one flagged in the pivot conversation as the
      natural schedule-triggered agent — e.g., a 9am daily run that
      publishes everything approved since the last run — while the other
      three Party sub-agents stay prompt-triggered.)*
  - **Item Request Agent** — orchestrates the full create/update/delete
    lifecycle for Item-type master data (e.g., product or SKU records),
    coordinating the same four sub-agent shape as Party. **Item is a new
    master data domain beyond the Party (customer/supplier) scope defined
    in the current backend schema** — schema extension needed. Per the
    2026-08-12 decision: design the schema/agent structure now, defer
    sourcing real Item data until Party-domain agents work end to end.
    - Item Insert and Update Agent
    - Item Action Recommendation Agent
    - Item Approval Tracking Agent
    - Item Downstream Agent
  - **Location Request Agent** — orchestrates the full create/update/delete
    lifecycle for Location-type master data (e.g., a new business location
    or facility), coordinating the same four sub-agent shape as Party.
    **Location is also a new master data domain beyond Party** — same
    schema-extension flag and same "design now, data later" treatment as
    Item. *(Note: this is also the domain used in the pivot conversation's
    worked example — "does this Alpharetta location already exist" —
    which the recommendation-sub-agent + relationship graph are meant to
    answer.)*
    - Location Insert and Update Agent
    - Location Action Recommendation Agent
    - Location Approval Tracking Agent
    - Location Downstream Agent

---

## Open items flagged directly in the source inventory

- Item and Location domains require a `mastered_entity` schema extension
  beyond what exists today (Party/GLEIF only) — confirmed as "design now,
  data later" per the 2026-08-12 decision.
- The exact shape of `resolution_request` / `entity_update_request` /
  `entity_deletion_request` / `review_queue_item` / `notification_task` as
  distinct record types is implied by the inventory's agent descriptions
  but not yet reflected in `backend/app/models.py` — needs schema design
  before the Request Agent branch can be built for real.
