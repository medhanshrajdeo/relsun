from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class SearchResult(BaseModel):
    id: int
    name: str
    domain: str
    match_type: Literal["Exact", "Similarity"]
    score: float


class MasterRecordDetail(BaseModel):
    id: int
    domain: str
    name: str
    external_id: str | None
    attributes: dict[str, Any]
    created_at: datetime


class CompareRecord(BaseModel):
    id: int
    name: str
    domain: str
    attributes: dict[str, Any]


class FieldDiff(BaseModel):
    key: str
    label: str
    values: dict[str, Any]  # record id (str) -> value, present only when set
    status: Literal["match", "partial", "conflict"]


class PairwiseMatch(BaseModel):
    record_a_id: int
    record_b_id: int
    score: float
    verdict: Literal["Likely duplicate", "Possibly related", "Likely distinct"]
    signals: dict[str, float | bool]
    rationale: str


class CompareResponse(BaseModel):
    records: list[CompareRecord]
    fields: list[FieldDiff]
    pairwise: list[PairwiseMatch]


class CompareSummaryResponse(BaseModel):
    summary: str


class GraphNode(BaseModel):
    id: int
    name: str | None
    domain: str | None
    lei: str | None
    is_anchor: bool
    existing_customer: bool


class GraphEdge(BaseModel):
    source: int
    target: int
    type: str
    properties: dict[str, Any]


class GraphResponse(BaseModel):
    center_id: int
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    truncated: bool


class ConciergeChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ConciergeChatRequest(BaseModel):
    prompt: str
    # Client-held conversation history (the frontend resends it each turn) —
    # deliberately not server-side persisted memory. Per-agent learning/
    # persistence is an explicitly open design question in the Agent
    # Architecture Pivot addendum; this is just enough continuity for a
    # real back-and-forth chat without prematurely solving that.
    history: list[ConciergeChatTurn] = []
    # The relationship graph currently rendered on the user's screen, if
    # any (the frontend sends the exact GraphResponse it already fetched —
    # see graph_context_agent.py for why this rides along instead of the
    # agent re-fetching from the DB). None on any non-graph page.
    graph_context: GraphResponse | None = None


class ConciergeChatResponse(BaseModel):
    response: str


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
    role: str | None


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: UserOut


class MasterDataRequestOut(BaseModel):
    id: int
    domain: str
    request_type: Literal["create", "update", "delete"]
    target_record_id: int | None
    proposed_attributes: dict[str, Any] | None
    status: Literal["pending", "approved", "rejected", "published"]
    decision_note: str | None
    submitted_at: datetime
    decided_at: datetime | None
    submitted_by: UserOut | None
    decided_by: UserOut | None


class DecideRequestBody(BaseModel):
    decision_note: str | None = None
