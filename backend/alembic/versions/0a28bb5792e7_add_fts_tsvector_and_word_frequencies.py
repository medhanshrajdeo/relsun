"""add fts tsvector column and word_frequencies table

Revision ID: 0a28bb5792e7
Revises: 4c2009b56c83
Create Date: 2026-08-11 23:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0a28bb5792e7'
down_revision: Union[str, None] = '4c2009b56c83'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 'simple' config deliberately, not 'english': company names are proper
    # nouns, not prose, and English stemming/stopword removal would distort
    # them (e.g. "Systems" and "System" should stay distinct terms here).
    op.execute(
        "ALTER TABLE master_records ADD COLUMN name_tsv tsvector "
        "GENERATED ALWAYS AS (to_tsvector('simple', name)) STORED"
    )
    op.execute("CREATE INDEX ix_master_records_name_tsv ON master_records USING gin (name_tsv)")

    # Corpus-wide document frequency per word, populated via ts_stat() (see
    # scripts/refresh_word_frequencies.py) — this is what search.py uses to
    # downweight common words ("Inc", "Group", ...) when scoring multi-word
    # queries, instead of a hardcoded stopword list.
    op.create_table(
        "word_frequencies",
        sa.Column("word", sa.String(length=255), primary_key=True),
        sa.Column("document_count", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("word_frequencies")
    op.execute("DROP INDEX IF EXISTS ix_master_records_name_tsv")
    op.execute("ALTER TABLE master_records DROP COLUMN IF EXISTS name_tsv")
