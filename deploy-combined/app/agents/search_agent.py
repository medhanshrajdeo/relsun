"""
Master Data Search Agent — wraps the existing, already-verified fuzzy
search (app/search.py's search_master_records) as a tool, per
AGENT_INVENTORY.md.

Accuracy note: the inventory also describes this agent triggering an "AI
web-search check" when an entity isn't found internally, to surface a
plausible existing relationship before Create. That fallback has no tool
behind it yet, so the instructions below deliberately don't mention it —
an agent's instructions should never describe a capability its tools
can't actually back up. For an MDM product whose whole pitch rests on
data being trustworthy, a confidently-invented "I checked the web and
found..." is worse than the agent just saying it doesn't have that yet.
"""

from sqlalchemy.orm import Session

from app.agents.framework import Agent, Tool
from app.search import search_master_records

SEARCH_INSTRUCTIONS = (
    "You are the Master Data Search Agent for an MDM (master data "
    "management) platform. You have one tool, search_master_data, which "
    "searches the platform's internal master records by name. It returns "
    "'Exact' matches (the name literally matches) and 'Similarity' "
    "matches (fuzzy/typo-tolerant, each with a 0-1 score), optionally "
    "restricted to one domain (e.g. 'Party'). Always call the tool before "
    "answering any question about whether an entity exists or what "
    "matches a name — never guess or answer from memory. Report results "
    "plainly: which records were found, their match type and score, and "
    "their domain. When you name a specific record that has an id, format "
    "its name as a markdown link in the exact form [Name](record:ID) — "
    "e.g. [Hanger, Inc.](record:2076447) — so the person reading your "
    "reply can click straight through to that record; do this every time "
    "you reference a record found by the tool, not just the first "
    "mention. If nothing is found, say so directly. You cannot "
    "create, update, or delete records, and you have no other data "
    "source beyond this internal search — if asked for something outside "
    "that, say plainly that it isn't available yet rather than "
    "attempting it."
)


def _search_handler(query: str, domain: str | None = None, *, session: Session, **_ignored) -> str:
    results = search_master_records(session, query, domain)
    if not results:
        return "No matching records found."
    return "\n".join(
        f"- {r.name} (id={r.id}, domain={r.domain}, {r.match_type} match, score={r.score:.2f})"
        for r in results
    )


search_tool = Tool(
    name="search_master_data",
    description=(
        "Search the platform's master data by name. Returns exact and "
        "fuzzy/typo-tolerant matches with scores, optionally filtered to "
        "one domain."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The entity name (or partial name) to search for."},
            "domain": {
                "type": "string",
                "description": "Optional domain to restrict the search to, e.g. 'Party'. Omit to search all domains.",
            },
        },
        "required": ["query"],
    },
    handler=_search_handler,
)

search_agent = Agent(name="master-data-search", instructions=SEARCH_INSTRUCTIONS, tools=[search_tool])
