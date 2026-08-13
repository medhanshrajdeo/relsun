# Relsun — Configurable Workflows & Agents Platform (Addendum)

This document extends CLAUDE.md. It captures a new, deliberate layer of the
product: rather than shipping fixed, one-size-fits-all workflows and AI
agents, Relsun exposes a **configuration layer** that each customer's own
developer can use to adapt workflows and agent behavior to their
organization — without needing to build MDM from the ground up themselves.

---

## 1. The core positioning shift

Relsun is not a fixed, ready-made solution — it's a **platform with strong
opinionated defaults** that a customer's developer can configure. Two
customers can both use Relsun, and end up with meaningfully different
systems, without either one custom-building from scratch.

**Why this matters commercially:** a customer with a technical team gets a
flexible platform they can shape to their exact process (workflow depth,
approval chains, agent behavior/verbosity). A customer without that
appetite gets a well-designed, working product out of the box, using
Relsun's baseline configuration. Both segments are served by the same
underlying product — this is the wedge that makes "start here instead of
building from the ground up" a persuasive pitch to a technical buyer, not
just a non-technical one.

**Explicit self-check to hold onto throughout this build:** the product
must NOT become "a thin UI wrapper around Microsoft Foundry" (or any
underlying agent platform). Wrapping an existing tool with a nicer UI is
not a defensible product. The real value has to come from:
- MDM-specific domain logic and defaults baked into the baseline
  workflows/agents (a generic agent platform doesn't know what a
  "location master data request" or "survivorship rule" is — Relsun does)
- The relationship-intelligence graph integration, which no generic
  workflow/agent tool provides
- A configuration UI that's genuinely easier and more purpose-fit for this
  domain than hand-editing raw agent instructions in a general-purpose
  tool

---

## 2. Two configurable surfaces

### A. Workflow configuration (MDM process logic)
Examples of what a customer's developer needs to be able to configure:
- Approval chains for master data requests (e.g., Customer A wants 4
  sequential approvals; Customer B wants a single policy-compliance check
  instead)
- Matching behavior/thresholds (e.g., how strict "similarity" match
  results are — exact-only vs. fuzzy-inclusive — configurable per
  domain/attribute, not just a fixed global setting)
- What triggers a request, what happens on approval/rejection, who gets
  notified

### B. Agent configuration (AI behavior)
Examples:
- The **Compare** feature's summarization agent — baseline instruction
  might be "summarize the difference in ~3 sentences," but one customer
  wants 10+ sentences of detail, another wants maximum brevity
- The **relationship intelligence** enrichment agent — how aggressively it
  surfaces external (D&B/web-search) suggestions, what confidence
  threshold triggers a suggestion
- Any future domain-specific agents (e.g., a request-triage agent, a
  duplicate-detection agent)

**Design principle to build around (validated by how Attio's own workflow
engine is built, worth reusing as a pattern):** separate the probabilistic
part from the deterministic part. An AI agent should **reason and draft**
(e.g., produce a comparison summary, suggest a relationship), but a
separate, deterministic step should **decide what gets written** to the
actual master data or graph. This keeps AI-generated output from silently
mutating governed data — the agent proposes, a controlled action block
commits. This is directly relevant to Relsun given the whole product's
credibility rests on data being trustworthy.

---

## 3. Technical approach: agents

> **⚠️ SUPERSEDED 2026-08-12** — see the "Agent Architecture Pivot"
> addendum at the bottom of this document. Foundry is no longer the
> runtime; it's a UX/architecture reference only. The rest of this
> section is kept for history — do not build against it.

**Decision: build agents directly in Python, not through Foundry's
no-code/portal configuration layer.**

Context: Microsoft's agent platform (now branded "Microsoft Foundry",
formerly "Azure AI Foundry" — both names still circulate) offers two
tiers:
- **Prompt agents** — configured entirely through the portal/SDK, no
  application code
- **Hosted agents** — code-based, using the Python (or C#/TypeScript/Java)
  SDK, used for production and custom-orchestration scenarios

Going Python-first, using **Foundry Hosted Agents** (Python SDK) or the
**Microsoft Agent Framework** (Microsoft's open-source, opinionated
framework unifying Semantic Kernel + AutoGen, stable across Python/.NET)
as the underlying execution layer, is the right call for two reasons:
1. It avoids the "just a wrapper around Foundry's UI" trap — Relsun's own
   product provides the customer-facing configuration UI; Foundry (or
   whichever agent runtime) is invisible infrastructure underneath, not
   something the customer configures directly
2. It keeps agent logic in the same language as the rest of the backend
   (Python/FastAPI, per CLAUDE.md), so agent code, matching logic, and API
   logic all live in one coherent codebase rather than split across a
   portal-configured tool and custom code

**What this means practically:** Relsun defines baseline agents (e.g., the
Compare summarizer) as Python code with parameterized instructions/config
(e.g., a `summary_length` or `verbosity` setting) rather than hardcoded
prompts. The customer-facing configuration UI (see below) writes to these
parameters — the customer's developer never touches Foundry directly, and
never edits raw prompt text unless Relsun explicitly chooses to expose
that as an "advanced" option later.

---

## 4. UX reference: Attio's workflow builder

> **⚠️ PARTIALLY SUPERSEDED 2026-08-12** — the block-based *visual
> sequence builder* idea below (Trigger → Logic → Action → AI, as a
> drag-and-drop canvas) is explicitly rejected by the Agent Architecture
> Pivot addendum at the bottom of this document — agentic workflows
> aren't a fixed sequence, so a sequence-builder UI is the wrong shape for
> configuring them. The one piece of this section that **still holds**:
> AI drafts, a separate deterministic step decides what gets written. That
> principle carries forward unchanged; only the "visual flow canvas" UX
> is dropped.

Attio (an AI-native CRM, not a direct competitor, but the closest
available reference for "customer-configurable workflows + agents done
well") is worth using as a direct UX pattern reference:
- **Visual, drag-and-drop workflow editor** — not a code editor, not a
  raw settings form
- **Block-based structure**: Trigger blocks (what starts a workflow) →
  Logic blocks (branching/conditions) → Action blocks (what happens:
  update a record, send a notification, call an external API) → AI blocks
  (an agent step that reasons/drafts)
- Critically: **AI blocks draft, they don't directly write.** A downstream
  deterministic "update block" commits the AI's output to actual records.
  This is the exact pattern to replicate for Relsun's agent-configuration
  UI, for the reasons in Section 2.
- Template workflows are offered as starting points customers can adapt,
  rather than requiring a blank-canvas build for every new customer

**Application to Relsun:** the eventual workflow/agent configuration
screen should follow this same block-based visual model — Trigger (e.g.,
"new master data request submitted") → Logic (e.g., "if domain = Location,
require 4 approvals") → Action (e.g., "distribute to downstream systems on
approval") → AI block (e.g., "run Compare summarization agent, verbosity =
customer setting").

---

## 5. Revised build sequence

> **⚠️ SUPERSEDED 2026-08-12** for Stage 2 onward — see the Agent
> Architecture Pivot addendum's "Revised build sequence" at the bottom of
> this document for the current plan. Stage 1 below is still accurate
> history (it's what actually got built) and is kept as-is.

This supersedes/extends the build order in CLAUDE.md Section 5. Confirmed
order, per direct instruction:

**Stage 1 (current focus — matches CLAUDE.md Phases 1-4):**
1. Get the right kind of seed data in place (mixed domains, realistic
   attributes)
2. Master Data Search + View Graph (relationship visualization working
   end to end)
3. A working summary agent for the Compare feature (baseline, fixed
   configuration for now — no customer configurability yet)

**Stage 2 — Foundry/Python agent integration + new-record workflow:**
4. Integrate the Python-based agent execution layer (Foundry Hosted
   Agents or Microsoft Agent Framework) properly, replacing any
   placeholder/simple LLM-call implementation of the Compare agent from
   Stage 1 with the real architecture this will scale on
5. Build the "create a brand new record" workflow end to end — a request
   is submitted, goes through an approval step, and (eventually)
   distributes on approval — this is the Master Data Requests phase from
   CLAUDE.md, now built with the real agent/workflow execution layer
   underneath rather than a stub

**Stage 3 — Customer-facing configuration layer (new scope, this
addendum's main subject):**
6. Design the front-end for workflow configuration — likely a
   block-based visual builder per Section 4, scoped initially to the
   specific configuration points already identified (approval chains,
   matching thresholds) rather than a fully generic workflow engine
7. Design the front-end for agent configuration — start with the
   simplest case (Compare agent verbosity/length as a configurable
   parameter) before generalizing to more agents
8. Determine how deep developer-level access goes (e.g., can they only
   adjust pre-defined parameters, or eventually write custom logic) —
   this is explicitly unresolved and should be scoped narrow first,
   widened only if real customer demand shows up for it

**Explicitly out of scope until Stage 3 is underway:** don't build a fully
generic, unlimited workflow/agent configuration engine speculatively.
Build the two concrete configuration cases already identified (approval
chains; agent summary verbosity) first, and generalize the underlying
architecture only once those two are working and real patterns emerge.

---

## 6. Open questions (not yet resolved — flag if asked, don't assume answers)

- Exactly how much configuration surface should be exposed to a
  customer's developer vs. kept as Relsun-controlled defaults — this is a
  product-scoping decision, not just a technical one, and directly
  affects how "opinionated platform" vs. "flexible toolkit" Relsun
  positions itself
- Whether advanced customers eventually get raw prompt/instruction
  editing access (bypassing the simplified configuration UI) — deferred,
  not decided
- Data requirements for demoing this to prospects — whether to use
  synthesized data or find a real/public dataset (e.g., public location
  data) for realistic demos — not yet resolved, worth revisiting once
  Stage 1 is functional and a real demo is being prepared

---

## Addendum: status as of 2026-08-12

Stage 1 items 1-2 (seed data, Search + View Graph) are done — see
CLAUDE.md's status table and DATA_STRATEGY.md's implementation addendum
for what actually got built (GLEIF bulk load, not the originally-imagined
hand-picked seed set; the search algorithm went through several rounds of
fixes beyond the original scope).

Stage 1 item 3 (Compare summary agent) is **scaffolded but not verified
working** — `app/agents/compare_summary.py`, the `/compare/summary`
endpoint, and the frontend UI (with a graceful "not configured" fallback)
all exist and follow the Section 3 Python-first architecture directly
(skipping the "placeholder/simple LLM-call implementation" Stage 1
originally allowed, going straight to the Foundry Hosted Agents SDK). But
no real Azure AI Foundry project/credentials have been configured in this
environment, so the agent has never actually been exercised end-to-end.
Do not count this as done until it has been run against a real Foundry
deployment. Standing rule from this point forward: never describe
integration code that exists-but-degrades-gracefully as a finished
feature — distinguish "the code path exists and is tested" from "the
actual feature has been exercised against its real dependency."

Stage 2 and Stage 3 are both fully unstarted.

---

## Addendum: Agent Architecture Pivot (2026-08-12)

This addendum captures a real architecture pivot, prompted by a founders'
conversation reviewing Microsoft Foundry's agent-portal UX and a full
agent inventory (`Relsun_Agents_Inventory.xlsx`, transcribed to
[`AGENT_INVENTORY.md`](./AGENT_INVENTORY.md)). It **replaces** Section 3
and the visual-builder part of Section 4 above, and **replaces** Stage 2
onward of Section 5's build sequence. Section 1 (core positioning),
Section 2 (two configurable surfaces), and the "AI drafts, deterministic
decides" principle in Section 4 are all still accurate and unchanged.

### The headline change

Two things pivoted together:

1. **No visual sequence builder.** The Sunday-era idea of a drag-and-drop
   Trigger → Logic → Action → AI workflow canvas (Section 4, Attio-style)
   is dropped entirely — not deferred, dropped. Real agentic systems
   don't execute a rigid step-1-then-step-2-then-step-3 chain; a
   step-1 agent doesn't need to know what a step-2 agent does. Building a
   UI to author a rigid chain would be building the wrong mental model
   into the product.
2. **Foundry is a UX/architecture reference, not a runtime dependency.**
   The founders' review of Foundry's agent portal — specifically, that an
   agent's "tools" list can include *other agents* — is what crystallized
   the hierarchy pattern below (the portal's own visualization, a master
   agent with blue sub-agent boxes hanging off it, is the direct visual
   inspiration for how Relsun should present its own agent hierarchy).
   But the actual runtime is **custom Python, calling an LLM API
   directly** (provider TBD — see Open Questions) — not Foundry Hosted
   Agents, not `azure-ai-agents`. This is a deliberate change from
   Section 3 above, confirmed 2026-08-12: keeping Foundry as a dependency
   didn't earn its complexity once the team decided not to lean on its
   no-code portal at all and wanted the agent-to-agent tool mechanism
   built and owned directly.

### The agent hierarchy pattern

Every agent in the system — see `AGENT_INVENTORY.md` for the full ~40-agent
tree across all four modules — is built the same way:

- **Python code**, not portal configuration.
- **Instructions**: a plain-English system prompt, editable by a
  customer's developer without touching code (this is what "no-code
  configuration" means now — see below).
- **Tools**: a list of things the agent can call. A tool is either a real
  function (a DB read/write, a graph query, sending a notification) *or
  another agent*, exposed as a callable tool exactly like Foundry's
  connected-agent pattern — just implemented in-house rather than via the
  Azure SDK.

Routing is a **runtime decision**, not a hardcoded chain: the calling
agent's instructions describe *when* to reach for which tool/sub-agent
("if the prompt is about search, use the Search Agent; if it's about
creating something new, use the Request Agent"), and the LLM decides at
call time based on the actual incoming prompt. The step-1 agent never
needs to know what step-2's agent does internally — it just knows *that*
it exists and *when* to hand off to it.

**Worked example** (from the founders' conversation, matches the Location
branch in `AGENT_INVENTORY.md`): a user asks whether an Alpharetta
location already exists. Concierge Agent detects domain = Location, hands
off to the Location Agent (Master Data Request Agent branch). Location
Agent detects intent = search, calls the Search Agent, which checks the
internal graph/DB first (per the existing "memory vs. Google" principle)
and responds. The user says "no, create a new one" — same Location Agent,
now detecting intent = creation, hands off to the Request Agent instead.
The Request Agent's four sub-agents (insert-and-update, recommendation,
approval-tracking, downstream) don't all fire in a fixed sequence either —
the Request Agent calls insert-and-update first because its own
instructions say to gather basic info before anything else, then decides
which of the remaining three to invoke based on what happens next (a
second approver showing up later triggers approval-tracking specifically,
not "step 3" by position).

### Trigger types

Three ways an agent chain gets kicked off — all three ultimately land as
a prompt at some agent's entry point, so the hierarchy itself doesn't need
to know which kind of trigger started it:

1. **User prompt** — free text or voice, the primary path.
2. **System-generated prompt** — a UI action (e.g., clicking "Approve" in
   a review queue) sends a predefined/canned prompt into the same
   Concierge-down-to-leaf-agent path a typed message would take. One
   entry mechanism, regardless of whether a human typed free text or
   clicked a button.
3. **Schedule** — some agents have no human prompt at all. The clearest
   case in the inventory is the **Party/Item/Location Downstream Agent**
   (publish approved changes to downstream systems) and the **Data
   Quality Checks Agent** (run each rule's validation query on schedule) —
   both are meant to run on a timer (e.g., every morning at 9am) rather
   than wait for a person. Mechanically this needs a scheduler that calls
   into the same agent entry point with a system-generated prompt — see
   Open Questions for the specific mechanism.

### Configurability, revised

Customer configuration is now **editing an agent's plain-English
instructions**, not building a flow diagram. Example unchanged from
Section 2: the Compare summary agent's baseline instruction says "about 3
sentences" — a customer who wants 2 just edits that one phrase. This is
still genuinely no-code (editing English, not editing a prompt DSL or
writing code), it's just relocated from "drag blocks on a canvas" to
"edit this agent's instructions." The product ships with a predefined
structure for ~5-6 master data domains (Party, Item, Location, +1-2 more
covers ~90% of companies per the founders' estimate); a customer either
uses the baseline instructions as-is or edits the wording to fit their
process.

**Learning over time:** each agent should carry conversation/outcome
memory so its routing and quality improve rather than repeating the same
mistake — and Relsun's own accumulated, refined instructions (matured
over months of real customer usage) become a real competitive moat, not
just the code. This is flagged as a real requirement but **not yet
designed** — see Open Questions.

### Revised build sequence (replaces Stage 2 onward above)

Confirmed 2026-08-12: **the Master Data branch is the only branch being
actively built next.** Data Catalog, Data Governance, and Data Quality
stay fully documented (`AGENT_INVENTORY.md`) but unbuilt, matching their
current "Soon" sidebar placeholders — do not start building agent code
for those three modules until Master Data's hierarchy is working.

1. ✅ **Done 2026-08-12 — replaced the Foundry-SDK scaffold, and built +
   verified the first real hierarchy slice.** `backend/app/agents/framework.py`
   is the shared `Agent`/`Tool`/`agent_as_tool()` harness every agent is
   built from (mocked-tested, `backend/tests/test_agent_framework.py`,
   4 tests, $0 API cost). `compare_summary.py` is rebuilt on it as a leaf
   agent. `search_agent.py` → `master_data_agent.py` → `concierge_agent.py`
   form the first real chain, exposed via `POST /concierge/chat`.
   **Verified against the live Anthropic API** (`claude-haiku-4-5-20251001`
   in this environment): 4 real prompts confirmed correct Search-tool
   routing, accurate results matching `GET /search` directly, honest
   "no matches found" with no hallucination, and a correct graceful
   decline (not an attempted fake action) when asked to create a record —
   the Master Data and Concierge instructions are deliberately scoped to
   only claim the tools actually wired in, per direct instruction ("make
   sure the instructions you give your agent are as accurate to the real
   product we want to build"). `azure-ai-agents` / `azure-identity` are
   fully dropped from `backend/requirements.txt`; `app/config.py` has
   `anthropic_api_key` / `anthropic_model` in place of the old Foundry
   settings. Frontend is **not** wired to `/concierge/chat` yet — Phase E
   of the build plan, still the static placeholder page.
2. ✅ **Done 2026-08-12 — Compare Agent built and verified.**
   `backend/app/agents/compare_agent.py` wraps `compare_records` (as the
   `compare_master_data` tool) and the `compare_summary` leaf agent (as
   `draft_compare_summary`, its first live caller) as tools on a new
   Master Data Compare Agent; `master_data_agent.py` gained a second
   sub-agent alongside Search, and resolves names to IDs via Search
   first when a comparison request only gives names — a real 3-4 hop
   chain the model assembles itself, nothing hardcoded. `render_compare_facts`
   was promoted from a private helper in `compare_summary.py` to a
   shared function in `app/compare.py` so the deterministic-tool output
   and the summary agent's input are rendered identically, not
   duplicated. Verified live: asked to compare "Hanger Inc" and "Hanger
   Solution" by name, it correctly overrode the raw name-similarity
   verdict ("Likely duplicate", 87%) using the field facts (different
   LEI/country/legal form) to report them as distinct — and explicitly
   declined to claim any ownership/relationship connection, matching the
   instruction that this agent has no graph access.
3. ✅ **Done 2026-08-13 — Party Request Agent branch built and verified.**
   Scoped down from the inventory's four Party sub-agents to one real LLM
   agent (`party_request_agent.py`) plus deterministic code
   (`app/requests.py`) — see that day's plan for the reasoning: the two
   moments that actually write to `master_records` should never be an
   LLM's call, only a human clicking Approve in the new Review Queue
   screen. No Recommendation Agent in this pass — the graph-access piece
   stays explicitly deferred, its own future scoping task, not folded in
   as a name-similarity wrapper. New tables: `master_data_requests`,
   `audit_log`; `master_records` gained `deleted_at` (soft-delete).
   Live-verified: create→approve produces a real record; create→reject
   never touches `master_records`; update/delete by name resolve via
   Search first (same bridge pattern as Compare) and apply correctly on
   approval. A real bug surfaced by the first-ever ORM insert in this
   codebase (`approve_request`'s create path) — see CLAUDE.md's status
   table for the `name_tsv`/`Computed()` fix.

   **No Approval Tracking Agent either**, worth being explicit about
   since the inventory implies one: nothing agentic "tracks" a request's
   status. `check_request_status` (a tool on the Party Request Agent) is
   a plain read-only lookup; the actual status transition
   (`approve_request`/`reject_request`) is deterministic code reachable
   *only* via `POST /requests/{id}/approve|reject`, which only the
   Review Queue's buttons call. No agent, ever, can approve or reject a
   request — that's a human-only action by construction, not just by
   convention.

   **Required-fields policy** (direct instruction, same day): create
   needs `name` + `country`, enforced in `submit_request` — not just
   suggested in the agent's instructions. `lei` is optional but, when
   given, is checked against every existing active record and rejected
   outright on a match (an exact LEI collision is decisive in a way name
   similarity never is), mapped to `master_records.external_id` on
   approval rather than left inside the JSON `attributes` blob. Checked
   at both submit and approve time — approve time is the one that
   actually matters (two pending requests can both still be pending when
   one gets approved first), submit time just fails fast.
4. **Design (not build) Item and Location.** Extend the `mastered_entity`
   schema and the agent structure to support Item and Location as
   domains — both are flagged in `AGENT_INVENTORY.md` as schema
   extensions beyond the current Party-only backend. Defer sourcing real
   data for either domain until the Party-domain agent hierarchy is
   solid; this mirrors the Data Strategy's real-data-only principle
   (don't fabricate Item/Location records just to have something to
   demo).
5. **Scheduling mechanism**, needed once the Downstream Agent is real: a
   lightweight in-process scheduler (e.g. APScheduler) is the likely
   default now that Foundry/Azure Functions aren't in the runtime at all —
   not yet decided, see Open Questions.
6. Everything from the original Stage 3 (customer-facing configuration
   UI) still applies conceptually but is much simpler now: no block-based
   visual builder to design — likely just a settings screen listing each
   agent with an editable instructions field. Still deferred until the
   Master Data hierarchy itself is solid, per the original "narrow first,
   widen only on demand" guidance.

### Open questions from this pivot

- ~~LLM provider for the custom runtime~~ **Resolved 2026-08-12: Anthropic
  Claude** (`anthropic` Python SDK, model `claude-sonnet-5` by default,
  see `app/config.py`'s `anthropic_model` setting). Native tool use
  supports the agent-as-tool pattern directly. `compare_summary.py` is
  rebuilt on this and is the reference implementation for the rest of the
  hierarchy.
- **Memory/persistence design** for per-agent conversation/outcome
  learning — likely a Postgres table logging interactions and outcomes,
  but the schema isn't designed yet.
- **Scheduler mechanism** for the Downstream and Data Quality Checks
  agents — APScheduler is the working assumption, not confirmed.
- **How deep the Recommendation sub-agents lean on the relationship
  graph** — the founders' conversation describes the Recommendation
  sub-agent drawing on the graph to suggest related entities (e.g., "this
  might be the same/related entity"), which is presumably the existing
  Neo4j `get_relationship_graph` query exposed as a tool — not yet
  designed as such.
- `resolution_request` / `entity_update_request` / `entity_deletion_request`
  / `review_queue_item` / `notification_task` — record types implied by
  the agent inventory's descriptions but not yet reflected in
  `backend/app/models.py`.
