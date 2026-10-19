"""Haystack wiring, without API keys or network."""

import asyncio
import os
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace

import pytest
from haystack import tracing
from haystack.components.generators.chat import MockChatGenerator

from app.ai.components import EMBEDDING_DIM, HashTextEmbedder
from app.ai.pipelines import build_ask_pipeline
from app.ai.providers import chat_generator, text_embedder
from app.auth import User, current_user
from app.config import settings
from app.main import app


class FakeSupabase:
    """Answers supabase.rpc("match_notes", ...).execute() with fixed rows."""

    def __init__(self, rows):
        self.rows, self.calls = rows, []

    def rpc(self, name, params):
        self.calls.append((name, params))

        async def execute():
            return SimpleNamespace(data=self.rows)

        return SimpleNamespace(execute=execute)


def echo_llm() -> MockChatGenerator:
    return MockChatGenerator(response_fn=lambda messages: messages[-1].text)


@pytest.mark.parametrize("provider", ["openai", "gemini"])
def test_provider_pipelines_build(monkeypatch, provider):
    monkeypatch.setattr(settings, "llm_provider", provider)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("GOOGLE_API_KEY", "test")

    embedder, llm = text_embedder("query"), chat_generator()
    if provider == "gemini":
        assert embedder._config["output_dimensionality"] == EMBEDDING_DIM
        assert embedder._config["task_type"] == "RETRIEVAL_QUERY"
    else:
        assert embedder.dimensions == EMBEDDING_DIM
    pipeline = build_ask_pipeline(FakeSupabase([]), embedder, llm)
    assert {"embedder", "retriever", "prompt_builder", "llm"} <= set(pipeline.graph.nodes)


def test_chat_model_override(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "chat_model", "my-model")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert chat_generator().model == "my-model"


def test_ask_pipeline_puts_retrieved_notes_in_prompt():
    rows = [
        {"id": 7, "content": "The wifi password is hunter2", "similarity": 0.9, "created_at": ""}
    ]
    supabase = FakeSupabase(rows)
    pipeline = build_ask_pipeline(supabase, HashTextEmbedder(), echo_llm())

    result = asyncio.run(
        pipeline.run_async(
            {
                "embedder": {"text": "what is the wifi password?"},
                "retriever": {"user_id": "u1"},
                "prompt_builder": {"question": "what is the wifi password?"},
            },
            include_outputs_from={"retriever"},
        )
    )

    prompt = result["llm"]["replies"][0].text
    assert "hunter2" in prompt and "what is the wifi password?" in prompt
    assert result["retriever"]["documents"][0].id == "7"
    name, params = supabase.calls[0]
    assert name == "match_notes" and params["match_user_id"] == "u1"
    assert len(params["query_embedding"]) == EMBEDDING_DIM


def test_langfuse_connector_added_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "langfuse_public_key", "pk-lf-test")
    monkeypatch.setattr(settings, "langfuse_secret_key", "sk-lf-test")
    monkeypatch.setattr(tracing.tracer, "is_content_tracing_enabled", False)
    # setenv first so monkeypatch also removes the value the code sets.
    monkeypatch.setenv("HAYSTACK_LANGFUSE_ENFORCE_FLUSH", "true")
    monkeypatch.delenv("HAYSTACK_LANGFUSE_ENFORCE_FLUSH")

    pipeline = build_ask_pipeline(FakeSupabase([]), HashTextEmbedder(), echo_llm())

    assert "tracer" in pipeline.graph.nodes
    assert tracing.tracer.is_content_tracing_enabled
    assert os.environ["HAYSTACK_LANGFUSE_ENFORCE_FLUSH"] == "false"


@pytest.fixture
def langfuse_rejecting_keys():
    """A stand-in Langfuse that answers 401 to everything, like one given wrong keys."""

    class Reject(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(401)
            self.end_headers()

        do_POST = do_GET

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Reject)
    # Not shut down: spans are exported when the process exits, after the test.
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_port}"


def test_ask_works_when_langfuse_rejects_keys(monkeypatch, langfuse_rejecting_keys):
    monkeypatch.setattr(settings, "langfuse_public_key", "pk-lf-test")
    monkeypatch.setattr(settings, "langfuse_secret_key", "sk-lf-test")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
    monkeypatch.setenv("LANGFUSE_BASE_URL", langfuse_rejecting_keys)
    # Tracing is global: put the previous tracer and flags back afterwards.
    monkeypatch.setattr(tracing.tracer, "actual_tracer", tracing.tracer.actual_tracer)
    monkeypatch.setattr(tracing.tracer, "is_content_tracing_enabled", False)
    monkeypatch.setenv("HAYSTACK_LANGFUSE_ENFORCE_FLUSH", "true")
    monkeypatch.delenv("HAYSTACK_LANGFUSE_ENFORCE_FLUSH")

    pipeline = build_ask_pipeline(FakeSupabase([]), HashTextEmbedder(), echo_llm())
    result = asyncio.run(
        pipeline.run_async(
            {
                "embedder": {"text": "q"},
                "retriever": {"user_id": "u1"},
                "prompt_builder": {"question": "q"},
            }
        )
    )

    assert result["llm"]["replies"][0].text
    assert result["tracer"]["trace_url"] == ""


def test_ask_without_llm_is_503(client):
    app.dependency_overrides[current_user] = lambda: User(id=uuid.uuid4())
    try:
        res = client.post("/api/ask", json={"question": "hi"})
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 503
