import json
from itertools import combinations

import jellyfish
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.embeddings import cosine_similarity, ensure_embeddings
from app.models import MasterRecord
from app.schemas import CompareResponse, CompareRecord, FieldDiff, PairwiseMatch
from app.search import PHONETIC_MATCH_FLOOR, SIMILARITY_THRESHOLD

# Verdict bands reuse the same composite score search.py already tunes
# against, so a record surfaced as a "Similarity" search hit and a "Likely
# duplicate" compare verdict are backed by the same number.
POSSIBLE_DUPLICATE_THRESHOLD = 0.5

FIELD_LABELS = {
    "lei": "LEI",
    "country": "Country",
    "city": "City",
    "status": "Status",
    "source": "Source",
    "source_system": "Source System",
    "duplicate_of": "Flagged Duplicate Of",
    "address": "Address",
    "belongs_to": "Belongs To",
}


def _label(key: str) -> str:
    return FIELD_LABELS.get(key, key.replace("_", " ").title())


def _format_value(value):
    # (name, domain) provenance tuples are stored as 2-element JSON arrays.
    if isinstance(value, list) and len(value) == 2 and all(isinstance(v, str) for v in value):
        return f"{value[0]} ({value[1]})"
    return value


def _pairwise_score(session: Session, a: MasterRecord, b: MasterRecord) -> tuple[float, dict]:
    name_jw = jellyfish.jaro_winkler_similarity(a.name.lower(), b.name.lower())
    trigram_sim = session.execute(select(func.word_similarity(a.name, b.name))).scalar_one()
    vector_sim = cosine_similarity(a.embedding, b.embedding)
    phonetic_match = jellyfish.metaphone(a.name) == jellyfish.metaphone(b.name)

    score = max(name_jw, trigram_sim or 0.0, vector_sim)
    if phonetic_match:
        score = max(score, PHONETIC_MATCH_FLOOR)

    signals = {
        "name_similarity": round(name_jw, 3),
        "trigram_similarity": round(trigram_sim or 0.0, 3),
        "vector_similarity": round(vector_sim, 3),
        "phonetic_match": phonetic_match,
    }
    return score, signals


def _verdict(score: float) -> str:
    if score >= SIMILARITY_THRESHOLD:
        return "Likely duplicate"
    if score >= POSSIBLE_DUPLICATE_THRESHOLD:
        return "Possibly related"
    return "Likely distinct"


def _provenance_notes(a: MasterRecord, b: MasterRecord) -> list[str]:
    notes = []
    for x, y in ((a, b), (b, a)):
        dup_of = x.attributes.get("duplicate_of")
        if isinstance(dup_of, list) and len(dup_of) == 2 and dup_of[0] == y.name and dup_of[1] == y.domain:
            notes.append(f'"{x.name}" was imported and flagged as a duplicate of "{y.name}"')
    return notes


def _rationale(a: MasterRecord, b: MasterRecord, score: float, signals: dict, verdict: str) -> str:
    reasons = []
    if signals["name_similarity"] >= 0.85:
        reasons.append("names are nearly identical character-for-character")
    if signals["trigram_similarity"] >= 0.5:
        reasons.append("substantial word overlap in the name")
    if signals["vector_similarity"] >= 0.85:
        reasons.append("semantically equivalent names")
    if signals["phonetic_match"]:
        reasons.append("names sound alike phonetically")

    provenance = _provenance_notes(a, b)

    sentence = f"{verdict} ({score:.0%} match)"
    detail_parts = reasons + provenance
    if detail_parts:
        sentence += ": " + "; ".join(detail_parts) + "."
    else:
        sentence += "."
    return sentence


def compare_records(session: Session, ids: list[int]) -> CompareResponse:
    # deleted_at excluded, same as search.py — comparing a soft-deleted
    # record would be misleading, and a missing id already surfaces as
    # the same "not found" error a truly nonexistent id would.
    records = session.query(MasterRecord).filter(MasterRecord.id.in_(ids), MasterRecord.deleted_at.is_(None)).all()
    by_id = {r.id: r for r in records}
    missing = [i for i in ids if i not in by_id]
    if missing:
        raise ValueError(f"record id(s) not found: {missing}")
    ordered = [by_id[i] for i in ids]
    ensure_embeddings(session, ordered)

    field_keys = list(dict.fromkeys(k for r in ordered for k in r.attributes.keys()))
    fields = []
    for key in field_keys:
        values = {str(r.id): _format_value(r.attributes.get(key)) for r in ordered}
        present = [v for v in values.values() if v is not None]
        if not present:
            continue
        distinct = {v if isinstance(v, str) else json.dumps(v, sort_keys=True) for v in present}
        if len(distinct) > 1:
            status = "conflict"
        elif len(present) < len(values):
            status = "partial"
        else:
            status = "match"
        fields.append(FieldDiff(key=key, label=_label(key), values=values, status=status))

    pairwise = []
    for a, b in combinations(ordered, 2):
        score, signals = _pairwise_score(session, a, b)
        verdict = _verdict(score)
        pairwise.append(
            PairwiseMatch(
                record_a_id=a.id,
                record_b_id=b.id,
                score=round(score, 3),
                verdict=verdict,
                signals=signals,
                rationale=_rationale(a, b, score, signals, verdict),
            )
        )
    pairwise.sort(key=lambda p: p.score, reverse=True)

    return CompareResponse(
        records=[CompareRecord(id=r.id, name=r.name, domain=r.domain, attributes=r.attributes) for r in ordered],
        fields=fields,
        pairwise=pairwise,
    )


def render_compare_facts(compare: CompareResponse) -> str:
    """Render this module's deterministic output as plain text. Shared by
    the compare_summary agent (drafts a narrative over it) and the Compare
    Agent's compare_master_data tool (returns it directly as the
    deterministic verdict) — one rendering, so the two never drift."""
    names_by_id = {r.id: r.name for r in compare.records}
    lines = [f"Records being compared: {', '.join(names_by_id.values())}", ""]

    conflicts = [f for f in compare.fields if f.status == "conflict"]
    partials = [f for f in compare.fields if f.status == "partial"]
    if conflicts:
        lines.append("Conflicting fields (values disagree across records):")
        for f in conflicts:
            values = ", ".join(f"{k}={v}" for k, v in f.values.items() if v is not None)
            lines.append(f"  - {f.label}: {values}")
    if partials:
        lines.append("Partially present fields (missing on some records):")
        for f in partials:
            values = ", ".join(f"{k}={v}" for k, v in f.values.items() if v is not None)
            lines.append(f"  - {f.label}: {values}")
    if not conflicts and not partials:
        lines.append("All comparable fields match across records.")

    lines.append("")
    lines.append("Pairwise match analysis:")
    for p in compare.pairwise:
        a = names_by_id.get(p.record_a_id, str(p.record_a_id))
        b = names_by_id.get(p.record_b_id, str(p.record_b_id))
        lines.append(f"  - {a} vs {b}: {p.verdict} ({p.score:.0%}) — {p.rationale}")

    return "\n".join(lines)
