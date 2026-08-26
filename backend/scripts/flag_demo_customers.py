"""
Mark a small, deliberately chosen handful of real, already-loaded GLEIF
entities as Relsun's own "existing customer" — per DATA_STRATEGY.md section
2/6, this is the ONE piece of invented data in the whole build, and it's
Relsun's own product metadata layered on top of real entities, not a
fabricated relationship. LEIs below were pulled from the GLEIF API directly
(see memory: dataset-gleif-corporate-hierarchy) so they're verified real.

Run after ingest_gleif_entities.py. Safe to re-run: idempotent per LEI.

Run from backend/ with: python -m scripts.flag_demo_customers
"""

from sqlalchemy.orm import Session

from app.db import engine
from app.models import MasterRecord

# LEI -> label, just for the printed confirmation
DEMO_CUSTOMER_LEIS = {
    "5493006MHB84DD0ZWV18": "Alphabet Inc.",
    "RVHJWBXLJ1RFUBSY1F30": "The Boeing Company",
    "787RXPR0UX0O0XUXPZ81": "Nike, Inc.",
}


def main() -> None:
    with Session(engine) as session:
        records = (
            session.query(MasterRecord)
            .filter(MasterRecord.external_id.in_(DEMO_CUSTOMER_LEIS.keys()))
            .all()
        )
        found_leis = {r.external_id for r in records}
        for record in records:
            record.attributes = {**record.attributes, "relationship_status": "existing_customer"}
            print(f"Flagged {record.name} ({record.external_id}) as existing_customer")

        session.commit()

        missing = DEMO_CUSTOMER_LEIS.keys() - found_leis
        if missing:
            print(f"WARNING: LEI(s) not found in master_records, skipped: {sorted(missing)}")


if __name__ == "__main__":
    main()
