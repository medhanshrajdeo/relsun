"""
Master Data Compare Agent — wraps the existing deterministic compare
engine (app/compare.py) and the compare_summary leaf agent as tools, per
AGENT_INVENTORY.md and the Compare Agent spec agreed 2026-08-12.

Accuracy note: the verdict this agent surfaces measures name/field
similarity only (Jaro-Winkler, trigram, vector cosine, phonetic) — it has
no access to the Neo4j relationship graph, so it must never claim two
entities are related through ownership or any other relationship. That's
the future Recommendation sub-agent's job (Party/Item/Location Request
branch, unbuilt), not this one's — the instructions below say so
explicitly rather than leaving it implicit.
"""

from sqlalchemy.orm import Session

from app.agents.compare_summary import compare_summary_agent
from app.agents.framework import Agent, Tool, agent_as_tool
from app.compare import compare_records, render_compare_facts

COMPARE_INSTRUCTIONS = (
    "You are the Master Data Compare Agent for an MDM (master data "
    "management) platform. You have two tools: compare_master_data, "
    "which takes 2 or more record IDs and returns deterministic "
    "field-by-field differences and a pairwise verdict (Likely duplicate "
    "/ Possibly related / Likely distinct, with a score and a stated "
    "reason); and draft_compare_summary, which turns comparison facts "
    "you already have into a short plain-English narrative — pass it "
    "the exact output of compare_master_data, verbatim, as its prompt. "
    "Always call compare_master_data first. Only call "
    "draft_compare_summary afterward if a narrative genuinely helps "
    "(e.g. several fields differ, or more than two records were "
    "compared) — for a simple check, the verdict alone is often enough. "
    "Never state a verdict or cite a difference compare_master_data "
    "didn't actually report. The verdict measures name and field "
    "similarity only — it says nothing about ownership or corporate "
    "relationships. If the field-level facts (e.g. different LEI, "
    "different country) point away from the name-similarity verdict, "
    "say so plainly rather than leading with the verdict alone. Never "
    "claim two entities are related through ownership, a parent "
    "company, or any other relationship — you have no access to that "
    "data."
)


def _compare_handler(ids: list[int], *, session: Session, **_ignored) -> str:
    try:
        result = compare_records(session, ids)
    except ValueError as exc:
        return str(exc)
    return render_compare_facts(result)


compare_tool = Tool(
    name="compare_master_data",
    description=(
        "Compare 2+ existing master data records by ID. Returns "
        "field-by-field differences and a pairwise duplicate/distinct "
        "verdict with score."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "ids": {
                "type": "array",
                "items": {"type": "integer"},
                "minItems": 2,
                "description": "The record IDs to compare (from a prior search).",
            }
        },
        "required": ["ids"],
    },
    handler=_compare_handler,
)

draft_summary_tool = agent_as_tool(
    compare_summary_agent,
    name="draft_compare_summary",
    description=(
        "Draft a short plain-English narrative summary from comparison "
        "facts you already have. Pass the exact output of "
        "compare_master_data as the prompt."
    ),
)

compare_agent = Agent(
    name="master-data-compare",
    instructions=COMPARE_INSTRUCTIONS,
    tools=[compare_tool, draft_summary_tool],
)
