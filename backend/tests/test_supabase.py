"""End-to-end against a running Supabase with migrations applied.

    supabase start
    eval "$(supabase status -o env --override-name api.url=SUPABASE_URL \
        --override-name auth.secret_key=SUPABASE_SECRET_KEY)"
    RUN_SUPABASE_TESTS=1 uv run pytest
"""

import os
import uuid

import pytest
from supabase import Client, ClientOptions, create_client

from app.config import settings

pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_SUPABASE_TESTS"), reason="set RUN_SUPABASE_TESTS=1 with Supabase running"
)

OPTIONS = ClientOptions(auto_refresh_token=False, persist_session=False)


def signed_in_user() -> tuple[str, Client]:
    """Create a confirmed user; return their access token and a client signed in as them."""
    email, password = f"test-{uuid.uuid4().hex}@example.com", uuid.uuid4().hex
    admin = create_client(settings.supabase_url, settings.supabase_secret_key, OPTIONS)
    admin.auth.admin.create_user({"email": email, "password": password, "email_confirm": True})
    user_client = create_client(settings.supabase_url, settings.supabase_secret_key, OPTIONS)
    session = user_client.auth.sign_in_with_password({"email": email, "password": password}).session
    assert session is not None
    return session.access_token, user_client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user():
    return signed_in_user()


def test_health_reports_database_ok(client):
    assert client.get("/api/health").json()["database"] == "ok"


def test_real_token_is_accepted_and_tampered_one_rejected(client, user):
    token, _ = user
    assert client.get("/api/me", headers=bearer(token)).status_code == 200
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    assert client.get("/api/me", headers=bearer(tampered)).status_code == 401


def test_create_list_and_search(client, user):
    headers = bearer(user[0])
    for text in ["the cat sat on the mat", "dogs love long walks", "tomato soup recipe"]:
        res = client.post("/api/notes", json={"content": text}, headers=headers)
        assert res.status_code == 201, res.text

    assert len(client.get("/api/notes", headers=headers).json()) == 3

    hits = client.get("/api/notes/search", params={"q": "cat on a mat"}, headers=headers)
    assert hits.status_code == 200, hits.text
    assert hits.json()[0]["content"] == "the cat sat on the mat"


def test_notes_are_scoped_to_user(client, user):
    client.post("/api/notes", json={"content": "private"}, headers=bearer(user[0]))
    other_token, _ = signed_in_user()
    assert client.get("/api/notes", headers=bearer(other_token)).json() == []


def test_browser_side_access_is_limited_by_rls(client, user):
    token, user_client = user
    client.post("/api/notes", json={"content": "mine"}, headers=bearer(token))
    other_token, _ = signed_in_user()
    client.post("/api/notes", json={"content": "theirs"}, headers=bearer(other_token))

    rows = user_client.table("notes").select("content").execute().data
    assert [r["content"] for r in rows] == ["mine"]

    with pytest.raises(Exception, match="permission denied"):
        user_client.rpc(
            "match_notes", {"query_embedding": [0] * 1536, "match_user_id": str(uuid.uuid4())}
        ).execute()


def test_ask_retrieves_only_own_notes(client, user):
    # Real Supabase retrieval; keyword-hash embeddings and an echoing fake LLM.
    from haystack.components.generators.chat import MockChatGenerator

    from app.ai.components import HashTextEmbedder
    from app.ai.pipelines import build_ask_pipeline

    headers = bearer(user[0])
    client.post("/api/notes", json={"content": "the spare key is under the mat"}, headers=headers)
    other_token, _ = signed_in_user()
    client.post(
        "/api/notes", json={"content": "the spare key is in the car"}, headers=bearer(other_token)
    )

    app = client.app
    llm = MockChatGenerator(response_fn=lambda messages: messages[-1].text)
    app.state.ask_pipeline = build_ask_pipeline(app.state.supabase, HashTextEmbedder(), llm)
    try:
        res = client.post("/api/ask", json={"question": "where is the spare key?"}, headers=headers)
    finally:
        app.state.ask_pipeline = None
    assert res.status_code == 200, res.text
    body = res.json()
    assert [s["content"] for s in body["sources"]] == ["the spare key is under the mat"]
    assert "under the mat" in body["answer"] and "in the car" not in body["answer"]
