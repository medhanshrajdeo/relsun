"""
Populate Postgres with Phase 1 seed data. Safe to re-run: clears
master_records first. Run from backend/ with: python -m scripts.seed
"""

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db import engine
from app.embeddings import embed_text
from app.models import MasterRecord
from scripts.seed_data import ENTITIES


def embedding_text(name: str, domain: str, attributes: dict) -> str:
    parts = [name, domain]
    if city := attributes.get("city"):
        parts.append(city)
    if country := attributes.get("country"):
        parts.append(country)
    if status := attributes.get("status"):
        parts.append(status)
    return " | ".join(parts)


GRAPH_ONLY_KEYS = {"duplicate_of", "belongs_to"}


def main() -> None:
    with Session(engine) as session:
        session.execute(delete(MasterRecord))

        for entity in ENTITIES:
            attributes = {k: v for k, v in entity["attributes"].items() if k not in GRAPH_ONLY_KEYS}
            text = embedding_text(entity["name"], entity["domain"], attributes)
            record = MasterRecord(
                name=entity["name"],
                domain=entity["domain"],
                attributes=attributes,
                embedding=embed_text(text),
            )
            session.add(record)

        session.commit()
        count = session.query(MasterRecord).count()
        print(f"Seeded {count} master records.")


if __name__ == "__main__":
    main()
