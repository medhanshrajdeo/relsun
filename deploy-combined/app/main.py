from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.agents.compare_summary import AgentNotConfiguredError, summarize_compare
from app.agents.concierge_agent import concierge_agent
from app.auth import InvalidCredentialsError, authenticate, create_session, invalidate_session
from app.compare import compare_records
from app.db import check_connection
from app.deps import get_bearer_token, get_current_user, get_session
from app.graph import DEFAULT_HOPS, DEFAULT_PATH_LIMIT, get_relationship_graph
from app.models import MasterRecord, User
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
    LoginRequest,
    LoginResponse,
    MasterDataRequestOut,
    MasterRecordDetail,
    SearchResult,
    UserOut,
)
from app.search import search_master_records

app = FastAPI(title="Relsun API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://relsun-frontend-7474659130414957.aws.databricksapps.com",
    ],
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


@app.post("/auth/login", response_model=LoginResponse)
def auth_login(body: LoginRequest, session: Session = Depends(get_session)):
    try:
        user = authenticate(session, body.username, body.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    user_session = create_session(session, user)
    return LoginResponse(token=user_session.token, user=UserOut.model_validate(user, from_attributes=True))


@app.post("/auth/logout")
def auth_logout(token: str = Depends(get_bearer_token), session: Session = Depends(get_session)):
    # Idempotent by design: an already-expired/unknown token is a no-op,
    # not an error — logging out should never itself be able to fail.
    invalidate_session(session, token)
    return {"status": "ok"}


@app.get("/auth/me", response_model=UserOut)
def auth_me(user: User = Depends(get_current_user)):
    return user


@app.get("/domains", response_model=list[str])
def domains(session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    # Deliberately not a fixed enum: Relsun has no baked-in taxonomy of what
    # domains exist — each tenant's loaded data defines its own (GLEIF gives
    # us "Party" only; a different customer's data may look nothing like
    # this). The UI reflects whatever's actually present, not a hardcoded list.
    rows = session.query(MasterRecord.domain).distinct().order_by(MasterRecord.domain).all()
    return [r[0] for r in rows]


@app.get("/search", response_model=list[SearchResult])
def search(
    q: str, domain: str | None = None, session: Session = Depends(get_session), user: User = Depends(get_current_user)
):
    return search_master_records(session, q, domain)


@app.get("/master-records/{record_id}", response_model=MasterRecordDetail)
def master_record_detail(
    record_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)
):
    # Backs the party detail modal — the "open record" action from Search
    # results and from a record link surfaced in a Concierge chat reply.
    # Read-only, same as everything else in this API except the request
    # approve/reject paths.
    record = session.get(MasterRecord, record_id)
    if record is None or record.deleted_at is not None:
        raise HTTPException(status_code=404, detail=f"master record {record_id} not found")
    return record


@app.get("/compare", response_model=CompareResponse)
def compare(
    ids: Annotated[list[int], Query()], session: Session = Depends(get_session), user: User = Depends(get_current_user)
):
    if len(ids) < 2:
        raise HTTPException(status_code=400, detail="Select at least 2 records to compare")
    try:
        return compare_records(session, ids)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/compare/summary", response_model=CompareSummaryResponse)
def compare_summary(
    ids: Annotated[list[int], Query()], session: Session = Depends(get_session), user: User = Depends(get_current_user)
):
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
def concierge_chat(
    body: ConciergeChatRequest, session: Session = Depends(get_session), user: User = Depends(get_current_user)
):
    # Stateless, single-turn for now — thread/session memory across turns
    # is an explicitly open design question in the Agent Architecture
    # Pivot addendum, not solved here. The Concierge Agent's own
    # instructions are the only thing that decides what gets called
    # underneath; this endpoint just hands the prompt off and reports the
    # final answer. current_user_id rides along in context so a Party
    # Request submitted through chat records who actually submitted it.
    try:
        response = concierge_agent.run(
            body.prompt,
            context={"session": session, "current_user_id": user.id},
            history=[turn.model_dump() for turn in body.history],
        )
    except AgentNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Concierge agent failed: {exc}")
    return ConciergeChatResponse(response=response)


@app.get("/requests", response_model=list[MasterDataRequestOut])
def requests_list(
    status: str | None = None, session: Session = Depends(get_session), user: User = Depends(get_current_user)
):
    # The Review Queue screen. Deliberately plain — no agent involved in
    # listing, same as reading anything else in this API.
    return list_requests(session, status=status)


@app.get("/requests/{request_id}", response_model=MasterDataRequestOut)
def requests_get(request_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    request = get_request(session, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail=f"request {request_id} not found")
    return request


@app.post("/requests/{request_id}/approve", response_model=MasterDataRequestOut)
def requests_approve(
    request_id: int,
    body: DecideRequestBody,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    # The only path in the whole codebase that can turn a pending request
    # into an actual master_records change — a human calling this
    # endpoint, never agent code. See requests.approve_request. The logged
    # -in user deciding is recorded as decided_by — this is what lets a
    # second user's login show up as the one who approved a first user's
    # submitted request in the Review Queue.
    try:
        return approve_request(session, request_id, decision_note=body.decision_note, decided_by_id=user.id)
    except RequestStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except RequestValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/requests/{request_id}/reject", response_model=MasterDataRequestOut)
def requests_reject(
    request_id: int,
    body: DecideRequestBody,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        return reject_request(session, request_id, decision_note=body.decision_note, decided_by_id=user.id)
    except RequestStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.get("/graph/{record_id}", response_model=GraphResponse)
def graph(
    record_id: int,
    hops: int = DEFAULT_HOPS,
    limit: int = DEFAULT_PATH_LIMIT,
    user: User = Depends(get_current_user),
):
    result = get_relationship_graph(record_id, hops=hops, limit=limit)
    if result is None:
        raise HTTPException(status_code=404, detail=f"record id {record_id} not found")
    return result
