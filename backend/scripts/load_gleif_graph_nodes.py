"""
Push every master_records row into Neo4j as an :Entity node. Run after
ingest_gleif_entities.py has populated Postgres.

Creates a uniqueness constraint on :Entity(master_record_id) first — without
it, every batched MERGE below would do a full node scan, which is fine at a
few thousand nodes but falls over completely at 3.4M.

Safe to re-run: MERGE is idempotent per master_record_id.

Run from backend/ with: python -m scripts.load_gleif_graph_nodes
"""

import time

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import engine
from app.graph import driver

BATCH_SIZE = 10_000
LOG_EVERY = 500_000


def ensure_constraint() -> None:
    with driver.session() as session:
        session.run(
            "CREATE CONSTRAINT entity_master_record_id IF NOT EXISTS "
            "FOR (n:Entity) REQUIRE n.master_record_id IS UNIQUE"
        )


def load_nodes_batch(tx, rows: list[dict]) -> None:
    tx.run(
        """
        UNWIND $rows AS row
        MERGE (n:Entity {master_record_id: row.id})
        SET n.name = row.name, n.domain = row.domain, n.lei = row.lei
        """,
        rows=rows,
    )


def main() -> None:
    ensure_constraint()

    started = time.monotonic()
    count = 0
    with Session(engine) as pg_session, driver.session() as neo_session:
        neo_session.run("MATCH (n:Entity) DETACH DELETE n")

        result = pg_session.execute(
            text("SELECT id, name, domain, external_id FROM master_records ORDER BY id")
        )
        batch = []
        for record_id, name, domain, external_id in result:
            batch.append({"id": record_id, "name": name, "domain": domain, "lei": external_id})
            if len(batch) >= BATCH_SIZE:
                neo_session.execute_write(load_nodes_batch, batch)
                count += len(batch)
                batch = []
                if count % LOG_EVERY < BATCH_SIZE:
                    elapsed = time.monotonic() - started
                    print(f"  {count:,} nodes loaded ({elapsed:.0f}s elapsed)")
        if batch:
            neo_session.execute_write(load_nodes_batch, batch)
            count += len(batch)

    elapsed = time.monotonic() - started
    print(f"Loaded {count:,} graph nodes in {elapsed:.0f}s.")


if __name__ == "__main__":
    main()
