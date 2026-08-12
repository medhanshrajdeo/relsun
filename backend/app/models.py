from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EMBEDDING_DIM = 384


class Base(DeclarativeBase):
    pass


class MasterRecord(Base):
    __tablename__ = "master_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(String(50), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    # LEI for GLEIF-sourced records; null for records with no external identifier
    # (e.g. synthetic demo duplicates). Used to upsert on re-ingest and to join
    # Level 2 relationship edges without a name-based lookup at bulk scale.
    external_id: Mapped[str | None] = mapped_column(String(20), unique=True, index=True, nullable=True)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    # Null until a search/compare actually touches this record — embeddings are
    # generated lazily on demand, not pre-computed for the full bulk-loaded set.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    # DB-computed (GENERATED ALWAYS AS ... STORED, see migration 0a28bb5792e7) —
    # never written from Python, just read for full-text search / ts_stat().
    name_tsv: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True, insert_default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class WordFrequency(Base):
    """Corpus-wide document frequency per word in master_records.name,
    populated via scripts/refresh_word_frequencies.py using Postgres's own
    ts_stat(). search.py uses this to downweight common words when scoring
    multi-word queries — not a hardcoded stopword list, so it generalizes to
    whatever naming conventions a given tenant's actual data has."""

    __tablename__ = "word_frequencies"

    word: Mapped[str] = mapped_column(String(255), primary_key=True)
    document_count: Mapped[int] = mapped_column(Integer)
