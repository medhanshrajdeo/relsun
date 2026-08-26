from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, Computed, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

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
    # Computed(), not insert_default=None: the latter forced an explicit NULL
    # into every INSERT, which Postgres rejects for a GENERATED column — never
    # hit before because GLEIF ingestion uses raw SQL, not the ORM; the first
    # ORM-level insert (requests.py's approve_request, for 'create' requests)
    # surfaced it immediately.
    name_tsv: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed("to_tsvector('simple', name)", persisted=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    # Null = active. Set on an approved 'delete' request — never hard-deleted,
    # since a real DELETE would orphan graph edges, embeddings, and anything
    # that referenced this id, and is the wrong default for governed data
    # someone might need to audit later. search.py filters these out.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RelationshipEdge(Base):
    """A directed ownership edge between two master_records (parent owns
    child), replacing the old Neo4j :OWNS relationship — see app/graph.py,
    which walks this table with a recursive CTE instead of Cypher. A
    parent/child pair can be both the direct AND ultimate parent (common
    when there's only one level of ownership), so both bases are flags on
    the same edge rather than separate rows."""

    __tablename__ = "relationship_edges"
    __table_args__ = (UniqueConstraint("parent_id", "child_id", name="uq_relationship_edges_parent_child"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_id: Mapped[int] = mapped_column(ForeignKey("master_records.id"), index=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("master_records.id"), index=True)
    is_direct_parent: Mapped[bool] = mapped_column(Boolean, default=False)
    is_ultimate_parent: Mapped[bool] = mapped_column(Boolean, default=False)
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


class User(Base):
    """A real, logged-in Relsun user — session-based auth (see app/auth.py),
    not RBAC: every logged-in user can do everything today, this just
    gives requests/approvals a real actor identity to record instead of
    the previous no-auth state. `role` is a display label only (e.g.
    "Sales Rep"), not an enforcement mechanism."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class UserSession(Base):
    """A server-side, revocable login session — an opaque bearer token the
    frontend holds, not a JWT, specifically so /auth/logout can actually
    invalidate it rather than merely having the client discard it."""

    __tablename__ = "user_sessions"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MasterDataRequest(Base):
    """A proposed create/update/delete to a master record, per the Party
    Request Agent build plan. Nothing here is applied to master_records
    until approve_request() runs (app/requests.py) — a human clicking
    Approve in the Review Queue is the only path that can ever do that.
    No related_record_id/recommendation columns: those belong to the
    still-unbuilt, graph-aware Recommendation Agent, not this pass."""

    __tablename__ = "master_data_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(String(50), index=True)
    request_type: Mapped[str] = mapped_column(String(20))  # 'create' | 'update' | 'delete'
    # Null for 'create'; the record being changed for 'update'/'delete'.
    target_record_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # New/changed field values for 'create'/'update'; null for 'delete'.
    proposed_attributes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Null-able: an agent-submitted request always has a submitter (the
    # logged-in user chatting with the Concierge), but nothing here forbids
    # a future non-chat submission path. Two separate FKs, not one
    # "actor_id" — the submitter and decider are commonly different users
    # by design (the whole point of the Review Queue).
    submitted_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    decided_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    submitted_by: Mapped["User | None"] = relationship(foreign_keys=[submitted_by_id])
    decided_by: Mapped["User | None"] = relationship(foreign_keys=[decided_by_id])


class AuditLog(Base):
    """Append-only trail, separate from MasterDataRequest.status (which
    changes over time) — this is the immutable record of what happened
    and when, for a product whose whole pitch rests on data being
    trustworthy and auditable."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(50))  # 'submitted' | 'approved' | 'rejected' | 'published'
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
