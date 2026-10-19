"""Token checks that fail before any call to Supabase."""

import base64
import json
import time

import pytest


def b64(obj: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()


def fake_jwt(header: dict | None = None, **claims) -> str:
    header = header or {"alg": "ES256", "typ": "JWT", "kid": "k"}
    return f"{b64(header)}.{b64(claims)}.c2ln"


def test_missing_token_is_rejected(client):
    assert client.get("/api/me").status_code == 401


@pytest.mark.parametrize(
    "token",
    [
        "not-a-jwt",
        fake_jwt(sub="u", exp=int(time.time()) - 10),
        fake_jwt(sub="u"),
        fake_jwt({"alg": "ES256"}, sub="u", exp=int(time.time()) + 60),
    ],
    ids=["garbage", "expired", "no-exp", "bad-header"],
)
def test_malformed_tokens_are_rejected(client, token):
    res = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
