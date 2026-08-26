from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import engine
from app.models import MasterRecord

MAX_HOPS = 3
DEFAULT_HOPS = 2
DEFAULT_PATH_LIMIT = 80


def get_relationship_graph(record_id: int, hops: int = DEFAULT_HOPS, limit: int = DEFAULT_PATH_LIMIT) -> dict | None:
    """Return the local relationship neighborhood around one entity: every
    node and edge reachable within `hops` steps, in any direction, over
    relationship_edges. Undirected on purpose, same as the Neo4j Cypher this
    replaced (`-[*1..N]-`, no arrow) — a different tenant's data may care
    about ownership in either direction from a given anchor.

    Returns None if the record doesn't exist. Walked as an iterative BFS
    (at most `hops` round trips, hops is small and bounded) rather than a
    single recursive CTE — simpler to bound safely: `limit` caps the total
    number of *nodes* admitted (not path count, unlike the old Cypher —
    Postgres has no equivalent of collecting bounded paths in one shot),
    which is what actually protects against a high-fan-out hub entity
    (thousands of subsidiaries) blowing up the response.
    """
    hops = max(1, min(hops, MAX_HOPS))

    with Session(engine) as session:
        anchor = session.get(MasterRecord, record_id)
        if anchor is None or anchor.deleted_at is not None:
            return None

        reachable_ids = {record_id}
        frontier = {record_id}
        truncated = False

        for _ in range(hops):
            if not frontier:
                break
            rows = session.execute(
                text(
                    "SELECT parent_id, child_id FROM relationship_edges "
                    "WHERE parent_id = ANY(:frontier) OR child_id = ANY(:frontier)"
                ),
                {"frontier": list(frontier)},
            ).all()

            next_frontier: set[int] = set()
            for parent_id, child_id in rows:
                next_frontier.add(parent_id)
                next_frontier.add(child_id)
            next_frontier -= reachable_ids

            room = limit - len(reachable_ids)
            if len(next_frontier) > room:
                truncated = True
                next_frontier = set(sorted(next_frontier)[: max(room, 0)])

            reachable_ids |= next_frontier
            frontier = next_frontier

        edge_rows = session.execute(
            text(
                "SELECT parent_id, child_id, is_direct_parent, is_ultimate_parent "
                "FROM relationship_edges WHERE parent_id = ANY(:ids) AND child_id = ANY(:ids)"
            ),
            {"ids": list(reachable_ids)},
        ).all()

        records = (
            session.query(MasterRecord)
            .filter(MasterRecord.id.in_(reachable_ids), MasterRecord.deleted_at.is_(None))
            .all()
        )

    nodes = [_serialize_node(record, is_anchor=(record.id == record_id)) for record in records]
    edges = [
        {
            "source": parent_id,
            "target": child_id,
            "type": "OWNS",
            "properties": {"is_direct_parent": is_direct, "is_ultimate_parent": is_ultimate},
        }
        for parent_id, child_id, is_direct, is_ultimate in edge_rows
    ]

    return {
        "center_id": record_id,
        "nodes": nodes,
        "edges": edges,
        "truncated": truncated,
    }


def _serialize_node(record: MasterRecord, is_anchor: bool) -> dict:
    return {
        "id": record.id,
        "name": record.name,
        "domain": record.domain,
        "lei": record.external_id,
        "is_anchor": is_anchor,
        "existing_customer": record.attributes.get("relationship_status") == "existing_customer",
    }
