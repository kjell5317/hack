import time
import uuid

import jwt
import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import make_token

client = TestClient(app)
USER_ID = uuid.uuid4()


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_me_returns_user_from_token():
    res = client.get("/api/me", headers=auth(make_token(USER_ID)))
    assert res.status_code == 200
    assert res.json()["id"] == str(USER_ID)


def test_missing_token_is_rejected():
    assert client.get("/api/me").status_code == 401


@pytest.mark.parametrize(
    "token",
    [
        jwt.encode({"sub": str(USER_ID), "aud": "authenticated"}, "wrong" * 8, "HS256"),
        make_token(USER_ID, aud="anon"),
        make_token(USER_ID, exp=int(time.time()) - 10),
        jwt.encode({"sub": str(USER_ID), "aud": "authenticated"}, None, algorithm="none"),
        "not-a-jwt",
    ],
    ids=["bad-signature", "wrong-audience", "expired", "alg-none", "garbage"],
)
def test_invalid_tokens_are_rejected(token):
    assert client.get("/api/me", headers=auth(token)).status_code == 401
