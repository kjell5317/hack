"""Runs against a real Supabase Postgres with migrations applied.

Locally: `supabase db start`, then `RUN_DB_TESTS=1 uv run pytest`.
CI does the same (see .github/workflows/ci.yml).
"""

import asyncio
import os
import uuid

import asyncpg
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from tests.conftest import make_token

pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_DB_TESTS"), reason="set RUN_DB_TESTS=1 with a database running"
)


async def _create_user(user_id: uuid.UUID) -> None:
    conn = await asyncpg.connect(settings.database_url)
    try:
        await conn.execute("insert into auth.users (id) values ($1)", user_id)
    finally:
        await conn.close()


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def headers():
    user_id = uuid.uuid4()
    asyncio.run(_create_user(user_id))
    return {"Authorization": f"Bearer {make_token(user_id)}"}


def test_health_reports_database_ok(client):
    assert client.get("/api/health").json()["database"] == "ok"


def test_create_list_and_search(client, headers):
    for text in ["the cat sat on the mat", "dogs love long walks", "tomato soup recipe"]:
        res = client.post("/api/notes", json={"content": text}, headers=headers)
        assert res.status_code == 201, res.text

    assert len(client.get("/api/notes", headers=headers).json()) == 3

    hits = client.get("/api/notes/search", params={"q": "cat on a mat"}, headers=headers)
    assert hits.status_code == 200, hits.text
    assert hits.json()[0]["content"] == "the cat sat on the mat"


def test_notes_are_scoped_to_user(client, headers):
    client.post("/api/notes", json={"content": "private"}, headers=headers)
    other = {"Authorization": f"Bearer {make_token(uuid.uuid4())}"}
    assert client.get("/api/notes", headers=other).json() == []
