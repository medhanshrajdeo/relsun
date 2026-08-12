import jellyfish
from sqlalchemy import case, literal, text as sa_text
from sqlalchemy.orm import Session
from sqlalchemy.sql.functions import func

from app.db import engine
from app.embeddings import cosine_similarity, embed_text, ensure_embeddings
from app.models import MasterRecord
from app.schemas import SearchResult

# --- Blocking (candidate generation) ---
# Cast a broad, cheap, index-backed net so a real (larger) table doesn't need
# a full scan. Recall-oriented on purpose: the scoring pass below is what
# actually decides what counts as a match.
# 0.3 matches pg_trgm's own default word_similarity_threshold — verified against
# realistic typos ("alphbet"->ALPHABET 0.55, "boeng"->BOEING 0.50, "gogle"->GOOGLE
# 0.63) with comfortable margin. A lower threshold was tried first (0.15, tuned
# against a 17-row demo set) but at 3.4M real rows it made the GIN trigram index
# match hundreds of thousands of rows, forcing a ~5-8s scan per search — 0.3 cuts
# that to ~300ms without losing any of the verified matches.
BLOCKING_TRIGRAM_MIN = 0.3
BLOCKING_VECTOR_MAX_DISTANCE = 0.9
# 150, not 50: since blocking now keys off a single (rarest) query word, a
# genuinely common anchor word can have 50+ exact ties (56 real companies
# contain the word "ALPHABET") — too small a limit meant the true best match
# could lose an arbitrary id-based tiebreak and never even reach scoring.
# Cheap to raise: the anchor-word query is index-ordered regardless of LIMIT.
BLOCKING_LIMIT = 150

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
EXACT_LIMIT = 25

# A query word that appears in this many-or-fewer records keeps full scoring
# weight; above that, its weight falls off as 1/frequency. Not a hardcoded
# stopword list — this has to work for whatever naming conventions a given
# customer's own data has (a manufacturing company's records might commonly
# contain "Industries" or "Systems", nothing to do with legal suffixes), so
# "how common is this word, actually, in this dataset" comes from real corpus
# statistics (word_frequencies, populated via Postgres's ts_stat() — see
# scripts/refresh_word_frequencies.py) rather than a guess.
RARE_WORD_FREQUENCY_BASELINE = 50


def _words(name: str) -> list[str]:
    return [w.strip(",.") for w in name.split() if w.strip(",.")]


def _word_frequencies_batch(words: set[str]) -> dict[str, int]:
    # One query for however many distinct words need a frequency this
    # search, not one query per word: the coverage-penalty check below needs
    # a frequency for every word of every candidate's name (hundreds of
    # mostly-distinct words per search), where per-word round trips — even
    # cheap, cached ones — added up to real seconds of overhead.
    if not words:
        return {}
    with engine.connect() as conn:
        rows = conn.execute(
            sa_text("SELECT word, document_count FROM word_frequencies WHERE word = ANY(:words)"),
            {"words": list(words)},
        ).all()
    return dict(rows)


def _weight_from_frequency(freq: int) -> float:
    return min(1.0, RARE_WORD_FREQUENCY_BASELINE / max(freq, 1))


def _score_candidate(
    query_words: list[str], weights: dict[str, float], name: str, trigram_word_sim: float, vector_similarity: float
) -> float:
    # Tokenize the query into words and score each one against its best-
    # matching word in the name, then combine with a weighted average (not a
    # flat max) — weighted by how rare each query word actually is. Without
    # this, a query like "alphbet inc" could hit a perfect 1.0 purely from
    # "inc" == "Inc" (shared by thousands of unrelated companies) while the
    # actually-distinctive word ("alphbet") matched nothing at all, burying
    # real near-exact matches under a pile of same-suffix ties. A rare word
    # matching well still dominates the average; a common word matching (or
    # not) barely moves it.
    name_words = _words(name)

    per_word_best = [
        (weights.get(qw.lower(), 1.0), max((jellyfish.jaro_winkler_similarity(qw.lower(), nw.lower()) for nw in name_words), default=0.0))
        for qw in query_words
    ]
    total_weight = sum(w for w, _ in per_word_best) or 1.0
    word_jw = sum(w * s for w, s in per_word_best) / total_weight

    phonetic_match = any(
        weights.get(qw.lower(), 1.0) >= 0.5 and jellyfish.metaphone(qw) == jellyfish.metaphone(nw)
        for qw in query_words
        for nw in name_words
    )

    score = max(word_jw, trigram_word_sim or 0.0, vector_similarity)
    if phonetic_match:
        score = max(score, PHONETIC_MATCH_FLOOR)

    # The reverse direction matters too: the above only asks "does every query
    # word have a good match somewhere in the name" — it never checks whether
    # the name has *extra* content the query never mentioned, so "ALPHABET
    # INC." and "ALPHABET MINERALS INC" scored identically for "alphbet inc"
    # even though one is an exact match and the other just happens to contain
    # the same two words. Apply the same rarity weighting the other way: a
    # name word that's both distinctive (rare) and unexplained by the query
    # pulls the score down; common leftover words ("The", "Company") barely
    # register, so "boeing" -> "THE BOEING COMPANY" isn't penalized for them.
    # (weights here already covers every candidate name word too — see the
    # batch fetch in search_master_records — so no per-word DB call here.)
    name_weights = {nw: weights.get(nw.lower(), 1.0) for nw in name_words}
    total_name_weight = sum(name_weights.values()) or 1.0
    matched_name_weight = sum(
        name_weights[nw] * max((jellyfish.jaro_winkler_similarity(qw.lower(), nw.lower()) for qw in query_words), default=0.0)
        for nw in name_words
    )
    coverage = matched_name_weight / total_name_weight

    return score * coverage


def search_master_records(
    session: Session, query: str, domain: str | None = None
) -> list[SearchResult]:
    base = session.query(MasterRecord)
    if domain:
        base = base.filter(MasterRecord.domain == domain)

    # ORDER BY is load-bearing here, not cosmetic: without it, Postgres is free
    # to return any arbitrary subset of matching rows once a LIMIT is applied,
    # and even here (no LIMIT) the row order itself isn't stable across runs —
    # the same query was visibly returning different results on repeat.
    #
    # Plain alphabetical order was worse than cosmetic, though: "nike" is a
    # literal substring of "klINIKEn" and "techNIKEr", and alphabetically
    # those coincidental matches sort before any real "Nike"-named company —
    # with enough of them, they filled the entire EXACT_LIMIT quota and
    # pushed "NIKE" itself out of the Exact bucket entirely (it then showed
    # up mislabeled as "Similarity 100%" via the fuzzy path instead). Rank by
    # relevance tier first — exact full match, then starts-with, then a real
    # whole-word match (via the same tsvector used for full-text search, so
    # "nike" matches the word "Nike" but not the "nike" hidden inside
    # "kliniken") — and only fall back to alphabetical among equally-relevant
    # names.
    exact_tier = case(
        (func.lower(MasterRecord.name) == query.lower(), 0),
        (MasterRecord.name.ilike(f"{query}%"), 1),
        (MasterRecord.name_tsv.op("@@")(func.plainto_tsquery("simple", query)), 2),
        else_=3,
    )
    exact_records = (
        base.filter(MasterRecord.name.ilike(f"%{query}%"))
        .order_by(exact_tier, func.length(MasterRecord.name), MasterRecord.name)
        .limit(EXACT_LIMIT)
        .all()
    )
    exact_ids = {record.id for record in exact_records}

    similarity_query = base
    if exact_ids:
        similarity_query = similarity_query.filter(MasterRecord.id.notin_(exact_ids))

    query_words = _words(query) or [query]
    query_word_freqs = _word_frequencies_batch({w.lower() for w in query_words})
    weights = {qw: _weight_from_frequency(query_word_freqs.get(qw.lower(), 0)) for qw in query_words}
    # The rarest query word carries almost all the useful signal — a word
    # like "LLC" satisfies the word-similarity threshold for tens of
    # thousands of unrelated rows, which made the *whole query string* an
    # unselective predicate: Postgres correctly estimated ~64K matching rows
    # for "firebase llc" and rationally chose a full sequential scan over
    # using the index at all, an 8s search for what should be instant.
    # Blocking (and the trigram score signal) key off this one word instead;
    # the weighted-average word_jw score below still considers every word.
    anchor_word = max(query_words, key=lambda w: weights[w])

    query_embedding = embed_text(query)
    trigram_word_sim = func.word_similarity(anchor_word, MasterRecord.name)
    vector_distance = MasterRecord.embedding.cosine_distance(query_embedding)

    # Two independent blocking passes, since most rows (bulk-loaded, never
    # searched before) have no embedding yet:
    #   - trigram pass needs no embedding, catches typo/substring overlap
    #   - vector pass is restricted to rows already embedded from a prior
    #     touch, catching semantic matches for names already "warmed up"
    # Candidates surfaced here get embedded (if they weren't already) before
    # scoring, so this query's own semantic score is accurate even for a
    # never-before-seen row surfaced purely via trigram overlap.
    # id is a tie-break, not just style: with 3.4M rows it's common for many
    # equally-valid matches to tie at the same trigram/vector score (e.g. ~10
    # real, distinct companies all literally contain the word "ALPHABET"), and
    # without a deterministic secondary key Postgres can return a different
    # subset of the tied rows on every execution.
    #
    # word_similarity() as a plain function call isn't index-accelerated —
    # Postgres has to evaluate it for every row, which is a ~3.4M-row
    # sequential scan. Its <% (boolean "is a word match") / <<-> (match
    # distance, for ORDER BY) operator forms ARE accelerated by the GIN
    # trigram index. SET LOCAL scopes the threshold GUC those operators read
    # to just this transaction. The exact float score is still pulled via
    # word_similarity() in the SELECT list — cheap once the candidate set is
    # already narrowed by the index — so composite scoring stays precise,
    # not just a boolean pass/fail.
    # SET doesn't accept bind parameters in Postgres — BLOCKING_TRIGRAM_MIN is
    # our own constant, not user input, so inlining it here is safe.
    session.execute(sa_text(f"SET LOCAL pg_trgm.word_similarity_threshold = {BLOCKING_TRIGRAM_MIN}"))
    trgm_candidates = (
        similarity_query.add_columns(trigram_word_sim.label("trgm"))
        .filter(literal(anchor_word).op("<%")(MasterRecord.name))
        .order_by(literal(anchor_word).op("<<->")(MasterRecord.name), MasterRecord.id)
        .limit(BLOCKING_LIMIT)
        .all()
    )
    vec_candidates = (
        similarity_query.filter(MasterRecord.embedding.isnot(None))
        .add_columns(vector_distance.label("vec_dist"))
        .filter(vector_distance < BLOCKING_VECTOR_MAX_DISTANCE)
        .order_by(vector_distance.asc(), MasterRecord.id)
        .limit(BLOCKING_LIMIT)
        .all()
    )

    records_by_id = {record.id: record for record, _ in trgm_candidates}
    records_by_id.update({record.id: record for record, _ in vec_candidates})
    trgm_by_id = {record.id: trgm for record, trgm in trgm_candidates}
    candidates = list(records_by_id.values())

    ensure_embeddings(session, exact_records + candidates)

    # Batched, not per-candidate: the coverage penalty in _score_candidate
    # needs a frequency for every word of every candidate's name — with
    # BLOCKING_LIMIT=150 candidates that's hundreds of mostly-distinct words,
    # and looking each one up individually (even cached) was the dominant
    # cost in this function. One query for the lot.
    name_words_all = {w.lower() for record in candidates for w in _words(record.name)}
    name_word_freqs = _word_frequencies_batch(name_words_all - set(weights.keys()))
    weights.update({w: _weight_from_frequency(f) for w, f in name_word_freqs.items()})
    weights.update({w: 1.0 for w in name_words_all if w not in weights})

    scored = [
        (
            record,
            _score_candidate(
                query_words,
                weights,
                record.name,
                trgm_by_id.get(record.id, 0.0),
                cosine_similarity(record.embedding, query_embedding),
            ),
        )
        for record in candidates
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
