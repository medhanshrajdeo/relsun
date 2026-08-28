"""
Master Data Graph Context Agent — lets the Data Concierge answer questions
grounded in the exact relationship graph currently rendered on the user's
screen, rather than a generic re-search. Modeled directly on
search_agent.py's one-tool pattern.

The graph payload never comes from a fresh DB query here: the frontend
already fetched it (GraphResponse, via GET /graph/{id}) to render the page,
and resends that exact object as `graph_context` on the chat request (see
ConciergeChatRequest.graph_context in schemas.py) — this agent only exists
to describe it in a way an LLM can reason over, not to look anything up.
That also means its answers are always about *this specific view* (the hop
radius the user has open), not the record's full graph — if asked about
something outside what's shown, it says so rather than guessing.
"""

from typing import Any

from app.agents.framework import Agent, Tool

GRAPH_CONTEXT_INSTRUCTIONS = (
    "You are the Master Data Graph Context Agent for an MDM (master data "
    "management) platform. You have one tool, get_graph_context, which "
    "describes the relationship graph currently displayed on the user's "
    "screen — always call it first, before answering anything. Answer "
    "using only what it returns: if a relationship, node, or entity isn't "
    "mentioned in that description, say plainly that it isn't visible in "
    "the current view (e.g. 'not shown at the current hop radius') rather "
    "than guessing or falling back to general knowledge. If the tool "
    "reports no graph is currently displayed, say so directly — don't "
    "attempt to describe a graph from memory of the conversation. When you "
    "reference a specific record, format it as a markdown link in the "
    "exact form [Name](record:ID), matching how the other Master Data "
    "sub-agents already do this."
)


def _describe_relationship(edge: dict[str, Any], anchor_id: int, node_names: dict[int, str]) -> str:
    other_id = edge["target"] if edge["source"] == anchor_id else edge["source"]
    direction = "owns" if edge["source"] == anchor_id else "is owned by"
    props = edge.get("properties") or {}
    direct = bool(props.get("is_direct_parent"))
    ultimate = bool(props.get("is_ultimate_parent"))
    if direct and ultimate:
        basis = "direct & ultimate parent"
    elif direct:
        basis = "direct parent"
    elif ultimate:
        basis = "ultimate parent"
    else:
        basis = edge.get("type", "related")
    name = node_names.get(other_id, f"id={other_id}")
    return f"- Anchor {direction} {name} (id={other_id}) — {basis}"


def _graph_context_handler(*, graph_context: dict[str, Any] | None = None, **_ignored) -> str:
    if not graph_context:
        return "No graph is currently displayed."

    nodes = graph_context.get("nodes") or []
    edges = graph_context.get("edges") or []
    center_id = graph_context.get("center_id")

    node_names = {n["id"]: n.get("name") or f"id={n['id']}" for n in nodes}
    anchor = next((n for n in nodes if n.get("is_anchor")), None)
    anchor_id = anchor["id"] if anchor else center_id
    anchor_name = node_names.get(anchor_id, f"id={anchor_id}")

    lines = [f'Currently displayed graph, centered on "{anchor_name}" (id={anchor_id}).']

    existing_customers = [n for n in nodes if n.get("existing_customer")]
    if existing_customers:
        flagged = ", ".join(f"{node_names[n['id']]} (id={n['id']})" for n in existing_customers)
        lines.append(f"Flagged as an existing customer in this view: {flagged}.")

    direct_edges = [e for e in edges if anchor_id in (e["source"], e["target"])]
    if direct_edges:
        lines.append(f"Relationships touching the anchor ({len(direct_edges)}):")
        lines.extend(_describe_relationship(e, anchor_id, node_names) for e in direct_edges)

    indirect_edges = [e for e in edges if e not in direct_edges]
    if indirect_edges:
        lines.append(f"Other relationships visible in this view ({len(indirect_edges)}):")
        for e in indirect_edges:
            src, tgt = node_names.get(e["source"], f"id={e['source']}"), node_names.get(e["target"], f"id={e['target']}")
            lines.append(f"- {src} -> {tgt} ({e.get('type', 'related')})")

    other_nodes = [n for n in nodes if n["id"] != anchor_id]
    lines.append(f"Total entities in this view: {len(nodes)} ({len(other_nodes)} besides the anchor).")

    return "\n".join(lines)


graph_context_tool = Tool(
    name="get_graph_context",
    description=(
        "Describe the relationship graph currently displayed on the "
        "user's screen — the anchor entity, which of the visible entities "
        "are flagged as existing customers, and how everything shown is "
        "related. Returns a message saying no graph is displayed if none is."
    ),
    input_schema={"type": "object", "properties": {}},
    handler=_graph_context_handler,
)

graph_context_agent = Agent(
    name="master-data-graph-context",
    instructions=GRAPH_CONTEXT_INSTRUCTIONS,
    tools=[graph_context_tool],
)
