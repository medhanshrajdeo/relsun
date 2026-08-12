from typing import Any, Literal

from pydantic import BaseModel


class SearchResult(BaseModel):
    id: int
    name: str
    domain: str
    match_type: Literal["Exact", "Similarity"]
    score: float


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
