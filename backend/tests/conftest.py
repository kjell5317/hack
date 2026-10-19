import os

# Settings are read at import time. Unit tests never reach Supabase; the
# integration tests (test_supabase.py) need real values in the environment.
os.environ.setdefault("SUPABASE_URL", "http://127.0.0.1:54321")
os.environ.setdefault("SUPABASE_SECRET_KEY", "unused-in-unit-tests")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c
