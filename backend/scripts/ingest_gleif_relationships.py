"""
Bulk-load the GLEIF Level 2 (RR-CDF) concatenated file as :OWNS edges in
Neo4j. Run after load_gleif_graph_nodes.py has populated the :Entity nodes.

Relationships are resolved from LEI to master_record_id in chunks via
Postgres (indexed on external_id) rather than building one giant in-memory
map for ~660K edges spanning up to ~1.3M distinct LEIs.

A parent/child pair can appear as both "direct" and "ultimate" (common when
there's only one level of ownership, so the direct parent IS the ultimate
parent) — both bases are recorded as boolean flags on the same edge rather
than overwriting each other.

Safe to re-run: MERGE is idempotent per (parent, child) pair.

Run from backend/ with: python -m scripts.ingest_gleif_relationships
"""

import time
import zipfile
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import engine
from app.gleif import iter_ownership_edges
from app.graph import driver

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "gleif"
LEVEL2_ZIP = DATA_DIR / "level2.zip"
BATCH_SIZE = 5_000
LOG_EVERY = 100_000


def resolve_ids(pg_session: Session, leis: set[str]) -> dict[str, int]:
    if not leis:
        return {}
    result = pg_session.execute(
        text("SELECT external_id, id FROM master_records WHERE external_id = ANY(:leis)"),
        {"leis": list(leis)},
    )
    return dict(result.all())


def write_edges_batch(tx, rows: list[dict]) -> None:
    tx.run(
        """
        UNWIND $rows AS row
        MATCH (a:Entity {master_record_id: row.parent_id})
        MATCH (b:Entity {master_record_id: row.child_id})
        MERGE (a)-[r:OWNS]->(b)
        SET r.is_direct_parent = coalesce(r.is_direct_parent, false) OR row.basis = 'direct',
            r.is_ultimate_parent = coalesce(r.is_ultimate_parent, false) OR row.basis = 'ultimate'
        """,
        rows=rows,
    )


def main() -> None:
    if not LEVEL2_ZIP.exists():
        raise SystemExit(f"Missing {LEVEL2_ZIP} — download the Level 2 concatenated file first.")

    started = time.monotonic()
    seen = 0
    written = 0
    skipped = 0

    with Session(engine) as pg_session, driver.session() as neo_session, zipfile.ZipFile(LEVEL2_ZIP) as z:
        with z.open(z.namelist()[0]) as f:
            batch: list[dict] = []

            def flush():
                nonlocal written, skipped
                if not batch:
                    return
                leis = {e["parent_lei"] for e in batch} | {e["child_lei"] for e in batch}
                ids = resolve_ids(pg_session, leis)
                rows = []
                for edge in batch:
                    parent_id = ids.get(edge["parent_lei"])
                    child_id = ids.get(edge["child_lei"])
                    if parent_id is None or child_id is None:
                        skipped += 1
                        continue
                    rows.append({"parent_id": parent_id, "child_id": child_id, "basis": edge["basis"]})
                if rows:
                    neo_session.execute_write(write_edges_batch, rows)
                    written += len(rows)
                batch.clear()

            next_log = LOG_EVERY
            for edge in iter_ownership_edges(f):
                batch.append(edge)
                seen += 1
                if len(batch) >= BATCH_SIZE:
                    flush()
                if seen >= next_log:
                    elapsed = time.monotonic() - started
                    print(f"  {seen:,} relationships seen, {written:,} edges written ({elapsed:.0f}s elapsed)")
                    next_log += LOG_EVERY
            flush()

    elapsed = time.monotonic() - started
    print(
        f"Processed {seen:,} relationship records -> {written:,} OWNS edges "
        f"({skipped:,} skipped, unresolved LEI) in {elapsed:.0f}s."
    )


if __name__ == "__main__":
    main()
