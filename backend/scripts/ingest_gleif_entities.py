"""
Bulk-load the GLEIF Level 1 (LEI-CDF) concatenated file into master_records.
No artificial narrowing: every entity in the file is loaded as domain
"Party" (GLEIF has no concept of customer/supplier — that's Relsun's own
metadata, applied separately by flag_demo_customers.py). Embeddings are left
null; they're generated lazily on first search/compare touch.

Safe to re-run: truncates master_records first (cascades to nothing; the
graph load and demo-augmentation scripts run after this and should be
re-run too if this is re-run).

Run from backend/ with: python -m scripts.ingest_gleif_entities
"""

import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg.types.json import Json

from app.gleif import iter_entities
from app.lakebase_auth import get_raw_dsn

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "gleif"
LEVEL1_ZIP = DATA_DIR / "level1.zip"
LOG_EVERY = 100_000


def _attributes(row: dict) -> dict:
    attrs = {
        "lei": row["lei"],
        "country": row["country"],
        "city": row["city"],
        "hq_country": row["hq_country"],
        "hq_city": row["hq_city"],
        "entity_category": row["entity_category"],
        "legal_form": row["legal_form"],
        "status": row["status"],
        "source": "gleif",
    }
    return {k: v for k, v in attrs.items() if v is not None}


def main() -> None:
    if not LEVEL1_ZIP.exists():
        raise SystemExit(f"Missing {LEVEL1_ZIP} — download the Level 1 concatenated file first.")

    started = time.monotonic()
    with psycopg.connect(get_raw_dsn()) as conn:
        with conn.cursor() as cur:
            # CASCADE also empties relationship_edges (FK'd to
            # master_records) — correct here since ingest_gleif_relationships
            # reloads it fresh right after this script per SETUP.md's
            # ingestion order.
            cur.execute("TRUNCATE TABLE master_records RESTART IDENTITY CASCADE")

        count = 0
        duplicates = 0
        seen_leis: set[str] = set()
        now = datetime.now(timezone.utc)
        with zipfile.ZipFile(LEVEL1_ZIP) as z, z.open(z.namelist()[0]) as f:
            with conn.cursor() as cur:
                with cur.copy(
                    "COPY master_records (domain, name, external_id, attributes, created_at) FROM STDIN"
                ) as copy:
                    for row in iter_entities(f):
                        # The concatenated file aggregates ~40 separate LOU exports and
                        # occasionally contains the same LEI twice (in-progress transfers,
                        # corrected re-publications). Keep first occurrence, skip the rest —
                        # external_id has a unique constraint, so a raw duplicate would abort
                        # the whole load otherwise.
                        if row["lei"] in seen_leis:
                            duplicates += 1
                            continue
                        seen_leis.add(row["lei"])
                        copy.write_row(("Party", row["name"][:255], row["lei"], Json(_attributes(row)), now))
                        count += 1
                        if count % LOG_EVERY == 0:
                            elapsed = time.monotonic() - started
                            print(f"  {count:,} entities loaded ({elapsed:.0f}s elapsed)")

        conn.commit()

    elapsed = time.monotonic() - started
    print(
        f"Loaded {count:,} master records from GLEIF Level 1 in {elapsed:.0f}s "
        f"({duplicates:,} duplicate LEIs in the source file skipped)."
    )


if __name__ == "__main__":
    main()
