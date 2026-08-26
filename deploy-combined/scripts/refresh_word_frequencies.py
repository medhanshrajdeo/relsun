"""
Populate word_frequencies from master_records.name_tsv via Postgres's own
ts_stat() — genuine corpus-wide document frequency per word, not a guess.
search.py uses this to downweight common words ("Inc", "Group", whatever
happens to be common in a given tenant's actual naming conventions) when
scoring multi-word search queries.

Safe to re-run: replaces the table contents. Re-run after any bulk data
load that changes master_records.name meaningfully.

Run from backend/ with: python -m scripts.refresh_word_frequencies
"""

import time

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import engine


def main() -> None:
    started = time.monotonic()
    with Session(engine) as session:
        session.execute(text("TRUNCATE TABLE word_frequencies"))
        session.execute(
            text(
                """
                INSERT INTO word_frequencies (word, document_count)
                SELECT word, ndoc FROM ts_stat('SELECT name_tsv FROM master_records')
                """
            )
        )
        session.commit()
        count = session.execute(text("SELECT count(*) FROM word_frequencies")).scalar_one()

    elapsed = time.monotonic() - started
    print(f"Refreshed {count:,} word frequencies in {elapsed:.0f}s.")


if __name__ == "__main__":
    main()
