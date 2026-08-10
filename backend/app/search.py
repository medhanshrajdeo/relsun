import jellyfish
from sqlalchemy import or_
from sqlalchemy.orm import Session
from sqlalchemy.sql.functions import func

from app.embeddings import embed_text
from app.models import MasterRecord
from app.schemas import SearchResult

# --- Blocking (candidate generation) ---
# Cast a broad, cheap, index-backed net so a real (larger) table doesn't need
# a full scan. Recall-oriented on purpose: the scoring pass below is what
# actually decides what counts as a match.
BLOCKING_TRIGRAM_MIN = 0.15
BLOCKING_VECTOR_MAX_DISTANCE = 0.9
BLOCKING_LIMIT = 50

# --- Scoring (fine-grained match decision) ---
# Composite score is the max across independent signals, each catching a
# different failure mode a single algorithm misses on its own:
#   - word Jaro-Winkler: character-level typos ("Boeng" -> "Boeing")
#   - trigram word_similarity: partial/substring spelling overlap
#   - vector cosine similarity: conceptual/semantic relatedness
#   - phonetic (metaphone) match: sounds-alike names spelled quite differently
# Thresholds were tuned empirically against the seeded dataset's known
# duplicate/typo pairs vs. unrelated records (see PR/commit notes).
SIMILARITY_THRESHOLD = 0.72
PHONETIC_MATCH_FLOOR = 0.6
SIMILARITY_LIMIT = 10


def _words(name: str) -> list[str]:
    return [w.strip(",.") for w in name.split() if w.strip(",.")]


def _score_candidate(query: str, name: str, trigram_word_sim: float, vector_distance: float) -> float:
    query_lower = query.lower()
    words = _words(name)

    word_jw = max((jellyfish.jaro_winkler_similarity(query_lower, w.lower()) for w in words), default=0.0)
    phonetic_match = any(jellyfish.metaphone(w) == jellyfish.metaphone(query) for w in words)
    vector_similarity = max(0.0, 1 - (vector_distance or 2.0) / 2)

    score = max(word_jw, trigram_word_sim or 0.0, vector_similarity)
    if phonetic_match:
        score = max(score, PHONETIC_MATCH_FLOOR)
    return score


def search_master_records(
    session: Session, query: str, domain: str | None = None
) -> list[SearchResult]:
    base = session.query(MasterRecord)
    if domain:
        base = base.filter(MasterRecord.domain == domain)

    exact_records = base.filter(MasterRecord.name.ilike(f"%{query}%")).all()
    exact_ids = {record.id for record in exact_records}

    similarity_query = base
    if exact_ids:
        similarity_query = similarity_query.filter(MasterRecord.id.notin_(exact_ids))

    query_embedding = embed_text(query)
    trigram_word_sim = func.word_similarity(query, MasterRecord.name)
    vector_distance = MasterRecord.embedding.cosine_distance(query_embedding)

    candidates = (
        similarity_query.add_columns(trigram_word_sim.label("trgm"), vector_distance.label("vec_dist"))
        .filter(or_(trigram_word_sim > BLOCKING_TRIGRAM_MIN, vector_distance < BLOCKING_VECTOR_MAX_DISTANCE))
        .limit(BLOCKING_LIMIT)
        .all()
    )

    scored = [
        (record, _score_candidate(query, record.name, trgm, vec_dist))
        for record, trgm, vec_dist in candidates
    ]
    scored = [(record, score) for record, score in scored if score >= SIMILARITY_THRESHOLD]
    scored.sort(key=lambda pair: pair[1], reverse=True)

    return [
        SearchResult(id=r.id, name=r.name, domain=r.domain, match_type="Exact", score=1.0)
        for r in exact_records
    ] + [
        SearchResult(id=record.id, name=record.name, domain=record.domain, match_type="Similarity", score=score)
        for record, score in scored[:SIMILARITY_LIMIT]
    ]
