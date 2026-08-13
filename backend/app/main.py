from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.agents.compare_summary import AgentNotConfiguredError, summarize_compare
from app.agents.concierge_agent import concierge_agent
from app.compare import compare_records
from app.db import check_connection
from app.deps import get_session
from app.graph import DEFAULT_HOPS, DEFAULT_PATH_LIMIT, get_relationship_graph
from app.models import MasterRecord
from app.requests import (
    RequestStateError,
    RequestValidationError,
    approve_request,
    get_request,
    list_requests,
    reject_request,
)
from app.schemas import (
    CompareResponse,
    CompareSummaryResponse,
    ConciergeChatRequest,
    ConciergeChatResponse,
    DecideRequestBody,
    GraphResponse,
    MasterDataRequestOut,
    SearchResult,
)
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


@app.post("/concierge/chat", response_model=ConciergeChatResponse)
def concierge_chat(body: ConciergeChatRequest, session: Session = Depends(get_session)):
    # Stateless, single-turn for now — thread/session memory across turns
    # is an explicitly open design question in the Agent Architecture
    # Pivot addendum, not solved here. The Concierge Agent's own
    # instructions are the only thing that decides what gets called
    # underneath; this endpoint just hands the prompt off and reports the
    # final answer.
    try:
        response = concierge_agent.run(
            body.prompt,
            context={"session": session},
            history=[turn.model_dump() for turn in body.history],
        )
    except AgentNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Concierge agent failed: {exc}")
    return ConciergeChatResponse(response=response)


@app.get("/requests", response_model=list[MasterDataRequestOut])
def requests_list(status: str | None = None, session: Session = Depends(get_session)):
    # The Review Queue screen. Deliberately plain — no agent involved in
    # listing, same as reading anything else in this API.
    return list_requests(session, status=status)


@app.get("/requests/{request_id}", response_model=MasterDataRequestOut)
def requests_get(request_id: int, session: Session = Depends(get_session)):
    request = get_request(session, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail=f"request {request_id} not found")
    return request


@app.post("/requests/{request_id}/approve", response_model=MasterDataRequestOut)
def requests_approve(request_id: int, body: DecideRequestBody, session: Session = Depends(get_session)):
    # The only path in the whole codebase that can turn a pending request
    # into an actual master_records change — a human calling this
    # endpoint, never agent code. See requests.approve_request.
    try:
        return approve_request(session, request_id, decision_note=body.decision_note)
    except RequestStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except RequestValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/requests/{request_id}/reject", response_model=MasterDataRequestOut)
def requests_reject(request_id: int, body: DecideRequestBody, session: Session = Depends(get_session)):
    try:
        return reject_request(session, request_id, decision_note=body.decision_note)
    except RequestStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.get("/graph/{record_id}", response_model=GraphResponse)
def graph(record_id: int, hops: int = DEFAULT_HOPS, limit: int = DEFAULT_PATH_LIMIT):
    result = get_relationship_graph(record_id, hops=hops, limit=limit)
    if result is None:
        raise HTTPException(status_code=404, detail=f"record id {record_id} not found")
    return result
