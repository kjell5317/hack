import time
import uuid

import jwt
import pytest

from app.config import settings

TEST_SECRET = "test-secret-with-at-least-32-characters"


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", TEST_SECRET)


def make_token(user_id: uuid.UUID, **overrides) -> str:
    claims = {
        "sub": str(user_id),
        "aud": "authenticated",
        "role": "authenticated",
        "email": "test@example.com",
        "exp": int(time.time()) + 3600,
        **overrides,
    }
    return jwt.encode(claims, TEST_SECRET, algorithm="HS256")
