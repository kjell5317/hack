"""Against a real local Supabase. `./hack test` starts it and sets the env for you.

By hand: supabase start, then
    eval "$(supabase status -o env --override-name api.url=SUPABASE_URL \
        --override-name auth.secret_key=SUPABASE_SECRET_KEY)"
    RUN_SUPABASE_TESTS=1 uv run pytest
"""

import os
import uuid

import pytest
from supabase import Client, ClientOptions, create_client

from app.core.config import settings

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


def test_health_reports_database_ok(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["database"] == "ok"


def test_real_token_is_accepted_and_tampered_one_rejected(client):
    token, _ = signed_in_user()
    me = client.get("/api/me", headers=bearer(token))
    assert me.status_code == 200 and me.json()["email"].startswith("test-")
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    assert client.get("/api/me", headers=bearer(tampered)).status_code == 401


def test_real_token_reaches_protected_domain_routes(client):
    token, _ = signed_in_user()
    client.app.state.chat_pipeline = None
    # Past auth (not 401): fails on the missing LLM instead.
    res = client.post("/api/playground/chat", json={"message": "hi"}, headers=bearer(token))
    assert res.status_code == 503
