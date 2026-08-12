from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.agents.compare_summary import AgentNotConfiguredError, summarize_compare
from app.compare import compare_records
from app.db import check_connection
from app.deps import get_session
from app.graph import DEFAULT_HOPS, DEFAULT_PATH_LIMIT, get_relationship_graph
from app.models import MasterRecord
from app.schemas import CompareResponse, CompareSummaryResponse, GraphResponse, SearchResult
from app.search import search_master_records

app = FastAPI(title="Relsun API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    try:
        check_connection()
        return {"status": "ok", "database": "connected"}
    except Exception as exc:
        return {"status": "error", "database": "disconnected", "detail": str(exc)}


@app.get("/domains", response_model=list[str])
def domains(session: Session = Depends(get_session)):
    # Deliberately not a fixed enum: Relsun has no baked-in taxonomy of what
    # domains exist — each tenant's loaded data defines its own (GLEIF gives
    # us "Party" only; a different customer's data may look nothing like
    # this). The UI reflects whatever's actually present, not a hardcoded list.
    rows = session.query(MasterRecord.domain).distinct().order_by(MasterRecord.domain).all()
    return [r[0] for r in rows]


@app.get("/search", response_model=list[SearchResult])
def search(q: str, domain: str | None = None, session: Session = Depends(get_session)):
    return search_master_records(session, q, domain)


@app.get("/compare", response_model=CompareResponse)
def compare(ids: Annotated[list[int], Query()], session: Session = Depends(get_session)):
    if len(ids) < 2:
        raise HTTPException(status_code=400, detail="Select at least 2 records to compare")
    try:
        return compare_records(session, ids)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/compare/summary", response_model=CompareSummaryResponse)
def compare_summary(ids: Annotated[list[int], Query()], session: Session = Depends(get_session)):
    # Separate from /compare on purpose: the deterministic comparison (field
    # diffs, pairwise verdicts) is the source of truth and stays fast/always
    # available; this AI-drafted narrative is a slower, optional enrichment
    # the frontend fetches lazily on top of it. Nothing here writes anything.
    if len(ids) < 2:
        raise HTTPException(status_code=400, detail="Select at least 2 records to compare")
    try:
        comparison = compare_records(session, ids)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    try:
        summary = summarize_compare(comparison)
    except AgentNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI summary failed: {exc}")

    return CompareSummaryResponse(summary=summary)


@app.get("/graph/{record_id}", response_model=GraphResponse)
def graph(record_id: int, hops: int = DEFAULT_HOPS, limit: int = DEFAULT_PATH_LIMIT):
    result = get_relationship_graph(record_id, hops=hops, limit=limit)
    if result is None:
        raise HTTPException(status_code=404, detail=f"record id {record_id} not found")
    return result
