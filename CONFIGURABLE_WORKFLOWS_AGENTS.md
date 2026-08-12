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
