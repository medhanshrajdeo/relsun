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

Runs on Foundry Hosted Agents (Python SDK), per the addendum's decision to
build agents in code rather than through Foundry's no-code portal layer.
"""

import threading

from azure.ai.agents import AgentsClient
from azure.ai.agents.models import ListSortOrder, MessageRole
from azure.identity import DefaultAzureCredential

from app.config import settings
from app.schemas import CompareResponse

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


class AgentNotConfiguredError(RuntimeError):
    """FOUNDRY_PROJECT_ENDPOINT isn't set — expected in local dev until a
    real Foundry project exists (see config.py)."""


_client: AgentsClient | None = None
_agent_id: str | None = None
_lock = threading.Lock()


def _get_client() -> AgentsClient:
    global _client
    if not settings.foundry_project_endpoint:
        raise AgentNotConfiguredError(
            "FOUNDRY_PROJECT_ENDPOINT is not set — the Compare AI summary isn't "
            "available until a Foundry project is configured."
        )
    if _client is None:
        _client = AgentsClient(
            endpoint=settings.foundry_project_endpoint,
            credential=DefaultAzureCredential(),
        )
    return _client


def _get_agent_id(client: AgentsClient) -> str:
    # Created once and reused for the process lifetime — an Agent is a
    # persistent Foundry-side resource, not something to recreate per request.
    global _agent_id
    if _agent_id is None:
        with _lock:
            if _agent_id is None:  # re-check inside the lock
                agent = client.create_agent(
                    model=settings.foundry_model_deployment,
                    name="relsun-compare-summary",
                    instructions=BASELINE_INSTRUCTIONS,
                )
                _agent_id = agent.id
    return _agent_id


def _compare_facts(compare: CompareResponse) -> str:
    """Render compare.py's deterministic output as plain text — the agent
    reasons over these facts, it never recomputes or second-guesses them."""
    names_by_id = {r.id: r.name for r in compare.records}
    lines = [f"Records being compared: {', '.join(names_by_id.values())}", ""]

    conflicts = [f for f in compare.fields if f.status == "conflict"]
    partials = [f for f in compare.fields if f.status == "partial"]
    if conflicts:
        lines.append("Conflicting fields (values disagree across records):")
        for f in conflicts:
            values = ", ".join(f"{k}={v}" for k, v in f.values.items() if v is not None)
            lines.append(f"  - {f.label}: {values}")
    if partials:
        lines.append("Partially present fields (missing on some records):")
        for f in partials:
            values = ", ".join(f"{k}={v}" for k, v in f.values.items() if v is not None)
            lines.append(f"  - {f.label}: {values}")
    if not conflicts and not partials:
        lines.append("All comparable fields match across records.")

    lines.append("")
    lines.append("Pairwise match analysis:")
    for p in compare.pairwise:
        a = names_by_id.get(p.record_a_id, str(p.record_a_id))
        b = names_by_id.get(p.record_b_id, str(p.record_b_id))
        lines.append(f"  - {a} vs {b}: {p.verdict} ({p.score:.0%}) — {p.rationale}")

    return "\n".join(lines)


def summarize_compare(compare: CompareResponse) -> str:
    """Raises AgentNotConfiguredError if Foundry isn't set up yet, or lets
    any Azure SDK error propagate — the caller (main.py) maps both to
    appropriate HTTP responses rather than this module deciding that."""
    client = _get_client()
    agent_id = _get_agent_id(client)

    thread = client.threads.create()
    client.messages.create(thread_id=thread.id, role="user", content=_compare_facts(compare))
    client.runs.create_and_process(thread_id=thread.id, agent_id=agent_id)

    messages = client.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)
    for message in messages:
        if message.role == MessageRole.AGENT and message.text_messages:
            return message.text_messages[-1].text.value.strip()

    raise RuntimeError("Compare summary agent returned no response.")
