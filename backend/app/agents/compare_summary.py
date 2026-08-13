"""
Compare summarization agent.

This is the "AI drafts, deterministic decides" pattern from the
Configurable Workflows & Agents addendum: compare.py already computed
field diffs and pairwise verdicts deterministically (the source of truth).
This agent only drafts a narrative summary *over those already-computed
facts* for a human to read — it never recomputes them, never sees raw
records beyond what compare.py extracted, and has no write path. Nothing
here can mutate master data or the graph.

Baseline instructions are fixed for now (Stage 1 scope, per CLAUDE.md's
build sequence). Stage 3 makes verbosity a per-customer config parameter;
until that config layer exists, the ~3-sentence baseline is hardcoded.

Built on app/agents/framework.py, per the 2026-08-12 Agent Architecture
Pivot: Foundry is a UX/architecture reference for the agent-hierarchy
pattern now, not a runtime dependency. This is a leaf agent — it has no
tools of its own — but it's still an Agent instance like everything else
in AGENT_INVENTORY.md, so it can itself be wrapped via agent_as_tool()
for the Master Data Compare Agent to call (see compare_agent.py).
"""

from app.agents.framework import Agent, AgentNotConfiguredError
from app.compare import render_compare_facts
from app.schemas import CompareResponse

__all__ = ["AgentNotConfiguredError", "compare_summary_agent", "summarize_compare"]

BASELINE_INSTRUCTIONS = (
    "You are a master data comparison assistant for an MDM (master data "
    "management) platform. You will be given structured, already-computed "
    "field-level differences and match-verdict data for a set of records. "
    "Write a concise summary, about 3 sentences, in plain English, "
    "highlighting the key differences and what a data steward should look "
    "at first. Only describe what is in the provided data — never invent "
    "facts, and never recommend merging, deleting, or overwriting any "
    "record; you are drafting a summary for a human to review, not taking "
    "an action."
)

compare_summary_agent = Agent(name="compare-summary", instructions=BASELINE_INSTRUCTIONS)


def summarize_compare(compare: CompareResponse) -> str:
    """Raises AgentNotConfiguredError if no API key is set yet, or lets any
    Anthropic SDK error propagate — the caller (main.py) maps both to
    appropriate HTTP responses rather than this module deciding that."""
    return compare_summary_agent.run(render_compare_facts(compare))
