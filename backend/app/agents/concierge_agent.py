"""
Data Concierge Agent — top-level orchestrator, per AGENT_INVENTORY.md.

Accuracy note: the inventory describes routing across Catalog,
Governance, Quality, and Master Data module agents. Only Master Data
exists as a real module agent right now, matching CLAUDE.md's status
table (Catalog/Governance/Quality are "Soon" placeholders with no agents
built). The instructions below only offer the Master Data hand-off and
say plainly when a request falls outside that, instead of claiming
modules that don't exist — see the same accuracy note in
master_data_agent.py and search_agent.py.
"""

from app.agents.framework import Agent, agent_as_tool
from app.agents.master_data_agent import master_data_agent

CONCIERGE_INSTRUCTIONS = (
    "You are the Data Concierge, the entry point for an AI-native MDM "
    "(master data management) platform. Right now the only module "
    "available to you is Master Data (covering Party, Item, and Location "
    "entities) — hand off to it via the master_data tool for anything "
    "about searching, comparing, or creating/updating/deleting master "
    "data records (note: as of now, searching, comparing, and Party "
    "create/update/delete requests are implemented underneath it — "
    "Item and Location requests are not yet, and no request is ever "
    "actually applied until a human approves it in the Review Queue; "
    "the Master Data agent itself will tell you if something goes "
    "beyond what's available). Data Catalog, Data Governance, and Data "
    "Quality are not built yet; if a request is clearly about one of those (e.g. "
    "glossary terms, data policies, quality rules), say plainly that "
    "module isn't available yet rather than guessing or pretending to "
    "help with it. Before asking the user to clarify, check the "
    "conversation history for what a reference like 'it', 'that "
    "company', or 'the second one' points to — e.g. if you just told the "
    "user a record's name and ID, a follow-up saying 'compare it with X' "
    "means that same record. The master_data tool only sees the "
    "self-contained request you send it, not the conversation history, "
    "so once you've resolved a reference, state it explicitly in what "
    "you hand off (e.g. 'compare Hanger Inc (id 2076447) with Hanger "
    "Solution'), not 'it'."
)

master_data_tool = agent_as_tool(
    master_data_agent,
    name="master_data",
    description=(
        "Hand off to the Master Data Handling Agent for anything about "
        "searching, comparing, or creating/updating/deleting Party, Item, "
        "or Location master data records."
    ),
)

concierge_agent = Agent(name="data-concierge", instructions=CONCIERGE_INSTRUCTIONS, tools=[master_data_tool])
