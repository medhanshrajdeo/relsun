import threading
from functools import lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session

from app.models import MasterRecord

MODEL_NAME = "all-MiniLM-L6-v2"

# FastAPI runs sync `def` endpoints in a thread pool, and all of them share
# this one cached model instance. SentenceTransformer.encode() isn't
# documented as thread-safe for concurrent calls on the same instance — under
# real concurrent load this was producing silently wrong embeddings (no
# exception, just numerically corrupted output), which made search results
# for the *same query* vary request to request depending on what else was
# encoding at the same moment. One inference at a time process-wide.
_model_lock = threading.Lock()


@lru_cache(maxsize=1)
def _model() -> SentenceTransformer:
    return SentenceTransformer(MODEL_NAME)


def embed_text(text: str) -> list[float]:
    with _model_lock:
        return _model().encode(text, normalize_embeddings=True).tolist()


def embedding_text(name: str, domain: str, attributes: dict) -> str:
    parts = [name, domain]
    if city := attributes.get("city"):
        parts.append(city)
    if country := attributes.get("country"):
        parts.append(country)
    if status := attributes.get("status"):
        parts.append(status)
    return " | ".join(parts)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a), np.array(b)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    return float(np.dot(va, vb) / denom) if denom else 0.0


def ensure_embeddings(session: Session, records: list[MasterRecord]) -> None:
    """Lazily compute + persist embeddings for any of the given records that
    don't have one yet. Embeddings are never pre-generated in bulk (the GLEIF
    load leaves ~3.3M rows unembedded) — this is the only place they get
    created, triggered by a record actually being searched or compared.

    Always commits, even when nothing was missing: this is the last thing
    search/compare do with the session, and leaving the transaction open
    would leave any earlier SET LOCAL (e.g. search's pg_trgm threshold)
    dangling on the pooled connection for the next unrelated request to
    inherit, since SET LOCAL only reverts when the transaction actually
    ends — this was silently corrupting later requests' results."""
    missing = [r for r in records if r.embedding is None]
    for record in missing:
        text = embedding_text(record.name, record.domain, record.attributes)
        record.embedding = embed_text(text)
    session.commit()
