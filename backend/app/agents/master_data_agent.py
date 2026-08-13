"""
Master Data Handling Agent — module-level orchestrator for Master Data,
per AGENT_INVENTORY.md.

Accuracy note: the inventory describes this agent coordinating Search,
Compare, and Request sub-agents across Party/Item/Location. All three are
now wired in for Party; Item/Location are data-deferred (no Request
sub-agents for those domains yet). The instructions below only claim the
sub-agents actually present in `tools` below — update this docstring and
the instructions together as more are added, so the two never drift out
of sync.

Compare and Request both need record IDs, not names — this agent is the
one that bridges that gap: it holds Search, so when a comparison or an
update/delete request only gives a name, it resolves that name via
master_data_search first, then calls the other sub-agent with the ID it
found. Nothing hardcodes that two-step order; it follows from the
instructions plus what a given prompt actually contains.
"""

from app.agents.compare_agent import compare_agent
from app.agents.framework import Agent, agent_as_tool
from app.agents.party_request_agent import party_request_agent
from app.agents.search_agent import search_agent

MASTER_DATA_INSTRUCTIONS = (
    "You are the Master Data Handling Agent for an MDM (master data "
    "management) platform, covering the Party, Item, and Location "
    "domains. You have three sub-agents available: "
    "\n\nmaster_data_search — looks up whether an entity already exists "
    "(search by name, fuzzy/typo-tolerant, optionally filtered to a "
    "domain). "
    "\n\nmaster_data_compare — evaluates whether specific records, by ID "
    "not name, are duplicates, related, or distinct. If asked to compare "
    "records by name, first use master_data_search to resolve each name "
    "to an ID, then call master_data_compare with those IDs. "
    "\n\nmaster_data_request — for Party records only (customers, "
    "suppliers, third parties); Item and Location aren't supported yet. "
    "Handles proposing a create, update, or delete — it never applies "
    "anything itself, only submits a pending proposal for review. Update "
    "and delete need a record ID, not just a name: if the user only gave "
    "a name, use master_data_search to resolve it first, the same way "
    "you do for compare. A create needs no prior ID. "
    "\n\nNone of your sub-agents can approve or reject a pending request "
    "— that only happens when a human reviews it in the Review Queue "
    "screen. If asked to approve/reject/finalize something, say plainly "
    "that has to happen there, not here."
)

master_data_search_tool = agent_as_tool(
    search_agent,
    name="master_data_search",
    description="Hand off to the Master Data Search Agent to look up whether an entity already exists in the platform.",
)

master_data_compare_tool = agent_as_tool(
    compare_agent,
    name="master_data_compare",
    description=(
        "Hand off to the Master Data Compare Agent to evaluate whether "
        "specific records (by ID) are duplicates, related, or distinct."
    ),
)

master_data_request_tool = agent_as_tool(
    party_request_agent,
    name="master_data_request",
    description=(
        "Hand off to the Party Request Agent to propose a create, update, "
        "or delete of a Party record. Only submits a pending proposal — "
        "never applies it."
    ),
)

master_data_agent = Agent(
    name="master-data-handling",
    instructions=MASTER_DATA_INSTRUCTIONS,
    tools=[master_data_search_tool, master_data_compare_tool, master_data_request_tool],
)
