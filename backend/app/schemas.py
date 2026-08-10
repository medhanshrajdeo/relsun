from typing import Literal

from pydantic import BaseModel


class SearchResult(BaseModel):
    id: int
    name: str
    domain: str
    match_type: Literal["Exact", "Similarity"]
    score: float
