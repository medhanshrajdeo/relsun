from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import check_connection

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
