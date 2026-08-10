from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.db import check_connection
from app.deps import get_session
from app.schemas import SearchResult
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


@app.get("/search", response_model=list[SearchResult])
def search(q: str, domain: str | None = None, session: Session = Depends(get_session)):
    return search_master_records(session, q, domain)
