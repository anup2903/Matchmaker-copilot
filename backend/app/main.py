from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.router import api_router
from app.core.config import get_settings
from app.db.session import get_engine

settings = get_settings()

app = FastAPI(
    title="Matchmaker Copilot API",
    version="0.1.0",
    description="Internal matchmaking intelligence prototype. AI suggests; the matchmaker decides.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _health() -> dict[str, str]:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        db = "ok"
    except Exception:  # noqa: BLE001 - health must never raise
        db = "unavailable"
    return {
        "status": "ok" if db == "ok" else "degraded",
        "database": db,
        # never expose the key itself, only whether the LLM path is live
        "llm_mode": "configured" if settings.llm_configured else "demo",
    }


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return _health()


@app.get("/api/health", tags=["health"])
def api_health() -> dict[str, str]:
    return _health()


app.include_router(api_router)
