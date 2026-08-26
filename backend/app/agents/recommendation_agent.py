"""
Recommendation Agent — Party's recommendation sub-agent (see
AGENT_INVENTORY.md / the pivot addendum's Party sub-agent list, and
design_recommendation_agent_party.md for the 2026-08-20 scoping
conversation this first slice implements).

Scope of THIS pass, deliberately narrow: real web search only, via
Anthropic's server-side web_search tool. It looks up open facts about a
named entity (e.g. headquarters address) and returns them as a suggestion
for Party Request Agent to relay — never a fact stated as certain, never
something submitted without the human still reviewing it in the Review
Queue.

NOT yet built here (still deferred, don't claim otherwise): the internal
graph lookup ("memory before Google"), D&B, and the full ownership-chain /
parent-child-location recommendation flow (e.g. "create Boeing Seattle as
the HQ, then Boeing Atlanta as a child branch") described in the design
conversation. Wiring those in is future work on this same agent, not a
rewrite.
"""

from app.agents.framework import Agent, Tool, agent_as_tool

WEB_SEARCH_TOOL = Tool(
    name="web_search",
    description="",
    input_schema={},
    handler=lambda **_ignored: (_ for _ in ()).throw(
        RuntimeError("web_search is a server-side tool; it should never reach a client handler")
    ),
    raw_schema={"type": "web_search_20260209", "name": "web_search", "max_uses": 5},
)

RECOMMENDATION_INSTRUCTIONS = (
    "You are the Recommendation Agent for an MDM (master data management) "
    "platform's Party domain. Given a company name (and whatever other "
    "details you're given), use web search to find real, current, "
    "verifiable facts about it that would help someone filling in a Party "
    "record — principally its headquarters address (street, city, "
    "state/region, country) and legal/trading name, plus anything else "
    "clearly relevant (industry, other office locations) if it comes up "
    "naturally in the search results. "
    "\n\nYou have web search only right now — no access to the internal "
    "master data graph and no D&B lookup, so you cannot say whether an "
    "entity already exists in Relsun or is connected to one that does; "
    "don't imply otherwise. "
    "\n\nAlways phrase findings as a suggestion sourced from a live web "
    "search, not a stated fact — the calling agent still has to offer it "
    "to a human, and nothing you find is written to master data by you or "
    "anyone downstream without a human approving it. If search turns up "
    "nothing solid or the results conflict, say that plainly rather than "
    "guessing an address. Be concise — a short list of fields and values, "
    "not a research report."
)

recommendation_agent = Agent(
    name="recommendation",
    instructions=RECOMMENDATION_INSTRUCTIONS,
    tools=[WEB_SEARCH_TOOL],
    max_tokens=4096,
)

get_recommendation_tool = agent_as_tool(
    recommendation_agent,
    name="get_recommendation",
    description=(
        "Look up real-world facts about a named company via web search (e.g. its headquarters address) "
        "to help suggest values for a Party create/update. Returns a suggestion to relay to the user for "
        "confirmation, not a verified fact — web search only, no internal graph or D&B access yet."
    ),
)
