import os
import sys
from pathlib import Path

# The suite always runs in demo mode (deterministic, no network), regardless of any developer .env.
# Set before importing app code so the cached Settings pick it up.
for _var in ("LLM_API_KEY", "LLM_MODEL", "LLM_BASE_URL"):
    os.environ[_var] = ""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "seed"))

import seed as seed_module  # noqa: E402

from app.api.feedback import provider_factory  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.llm.demo import DemoProvider  # noqa: E402


@pytest.fixture(autouse=True)
def _no_retry_delay(monkeypatch):
    from app.services import feedback_structurer

    monkeypatch.setattr(feedback_structurer, "RETRY_DELAY_SECONDS", 0)


@pytest.fixture()
def session_factory():
    """Fresh in-memory SQLite database, seeded with the full mock dataset, per test."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        seed_module.seed_database(session)
    yield factory
    engine.dispose()


@pytest.fixture()
def db(session_factory):
    with session_factory() as session:
        yield session


@pytest.fixture()
def client(session_factory):
    def _get_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    # no LLM key in tests: always the deterministic demo provider unless a test overrides it
    app.dependency_overrides[provider_factory] = lambda: (lambda force_demo: DemoProvider())
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def ids(client):
    """name -> uuid for the seeded clients and candidates."""
    clients = {c["name"]: c["id"] for c in client.get("/api/clients").json()}
    candidates = {c["name"]: c["id"] for c in client.get("/api/candidates").json()}
    return {"clients": clients, "candidates": candidates}
