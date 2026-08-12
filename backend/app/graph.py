from neo4j import GraphDatabase

from app.config import settings

driver = GraphDatabase.driver(
    settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
)

MAX_HOPS = 3
DEFAULT_HOPS = 2
DEFAULT_PATH_LIMIT = 80


def get_relationship_graph(record_id: int, hops: int = DEFAULT_HOPS, limit: int = DEFAULT_PATH_LIMIT) -> dict | None:
    """Return the local relationship neighborhood around one entity: every
    node and edge reachable within `hops` steps, in any direction, over any
    relationship type. Deliberately not scoped to :OWNS specifically — a
    different tenant's data may use entirely different relationship types
    (SUPPLIES_TO, BELONGS_TO, ...), and this should surface all of them.

    Returns None if the record doesn't exist. `hops` is clamped to
    [1, MAX_HOPS] — Cypher variable-length relationship bounds must be a
    literal, not a query parameter, so it's interpolated after clamping
    (safe: it's a validated small int, never raw user text).
    """
    hops = max(1, min(hops, MAX_HOPS))

    with driver.session() as session:
        anchor_result = session.run(
            "MATCH (n:Entity {master_record_id: $id}) RETURN n", id=record_id
        ).single()
        if anchor_result is None:
            return None
        anchor = anchor_result["n"]

        # LIMIT bounds the number of expansion rows (one per path) explored
        # before aggregation, so a high-fan-out hub entity (thousands of
        # subsidiaries) doesn't return an unusably huge or slow response.
        result = session.run(
            f"""
            MATCH (anchor:Entity {{master_record_id: $id}})
            OPTIONAL MATCH p = (anchor)-[*1..{hops}]-(other:Entity)
            WITH p
            LIMIT $limit
            RETURN collect(p) AS paths
            """,
            id=record_id,
            limit=limit,
        ).single()

    paths = [p for p in result["paths"] if p is not None]

    nodes_by_id: dict[int, dict] = {
        anchor["master_record_id"]: _serialize_node(anchor, is_anchor=True)
    }
    edges_by_key: dict[tuple, dict] = {}

    for path in paths:
        for node in path.nodes:
            nodes_by_id.setdefault(node["master_record_id"], _serialize_node(node, is_anchor=False))
        for rel in path.relationships:
            source_id = rel.start_node["master_record_id"]
            target_id = rel.end_node["master_record_id"]
            key = (source_id, target_id, rel.type)
            edges_by_key[key] = {
                "source": source_id,
                "target": target_id,
                "type": rel.type,
                "properties": dict(rel),
            }

    return {
        "center_id": record_id,
        "nodes": list(nodes_by_id.values()),
        "edges": list(edges_by_key.values()),
        "truncated": len(paths) >= limit,
    }


def _serialize_node(node, is_anchor: bool) -> dict:
    return {
        "id": node["master_record_id"],
        "name": node.get("name"),
        "domain": node.get("domain"),
        "lei": node.get("lei"),
        "is_anchor": is_anchor,
        "existing_customer": bool(node.get("existing_customer", False)),
    }
