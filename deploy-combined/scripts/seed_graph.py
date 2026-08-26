"""
Populate Neo4j with Phase 1 relationship edges, referencing the Postgres
master_records seeded by scripts/seed.py. Run seed.py first.
Safe to re-run: clears all nodes/edges first.
Run from backend/ with: python -m scripts.seed_graph
"""

from sqlalchemy.orm import Session

from app.db import engine
from app.graph import driver
from app.models import MasterRecord
from scripts.seed_data import COMMERCIAL_EDGES, ENTITIES, OWNERSHIP_EDGES


def load_record_ids(session: Session) -> dict[tuple[str, str], int]:
    records = session.query(MasterRecord.id, MasterRecord.name, MasterRecord.domain).all()
    return {(name, domain): record_id for record_id, name, domain in records}


def upsert_node(tx, record_id: int, name: str, domain: str) -> None:
    tx.run(
        """
        MERGE (n:Entity {master_record_id: $record_id})
        SET n.name = $name, n.domain = $domain
        """,
        record_id=record_id,
        name=name,
        domain=domain,
    )


def upsert_edge(tx, from_id: int, to_id: int, rel_type: str) -> None:
    tx.run(
        f"""
        MATCH (a:Entity {{master_record_id: $from_id}})
        MATCH (b:Entity {{master_record_id: $to_id}})
        MERGE (a)-[:{rel_type}]->(b)
        """,
        from_id=from_id,
        to_id=to_id,
    )


def main() -> None:
    with Session(engine) as pg_session:
        ids = load_record_ids(pg_session)

    with driver.session() as neo_session:
        neo_session.run("MATCH (n) DETACH DELETE n")

        for entity in ENTITIES:
            key = (entity["name"], entity["domain"])
            neo_session.execute_write(upsert_node, ids[key], *key)

        for parent_name, parent_domain, child_name, child_domain in OWNERSHIP_EDGES:
            neo_session.execute_write(
                upsert_edge, ids[(parent_name, parent_domain)], ids[(child_name, child_domain)], "OWNS"
            )

        for from_name, from_domain, to_name, to_domain, rel_type in COMMERCIAL_EDGES:
            neo_session.execute_write(
                upsert_edge, ids[(from_name, from_domain)], ids[(to_name, to_domain)], rel_type
            )

        for entity in ENTITIES:
            entity_key = (entity["name"], entity["domain"])

            if belongs_to := entity["attributes"].get("belongs_to"):
                neo_session.execute_write(
                    upsert_edge, ids[entity_key], ids[tuple(belongs_to)], "BELONGS_TO"
                )

            if duplicate_of := entity["attributes"].get("duplicate_of"):
                neo_session.execute_write(
                    upsert_edge, ids[entity_key], ids[tuple(duplicate_of)], "POSSIBLE_DUPLICATE_OF"
                )

    node_count = len(ids)
    print(f"Seeded {node_count} graph nodes.")


if __name__ == "__main__":
    main()
