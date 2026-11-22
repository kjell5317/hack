"""Haystack wiring and the playground API, without API keys or network."""

import asyncio
import importlib
import os
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from haystack import component, tracing
from haystack.components.generators.chat import MockChatGenerator
from haystack.dataclasses import ChatMessage

from app.core import config
from app.core.ai import providers
from app.core.ai.hash_embedder import EMBEDDING_DIM, HashTextEmbedder
from app.core.auth import User, current_user
from app.core.config import settings
from app.domains.playground.pipeline import build_chat_pipeline
from app.main import app

KEYS = {
    "anthropic_api_key": "ANTHROPIC_API_KEY",
    "openai_api_key": "OPENAI_API_KEY",
    "google_api_key": "GOOGLE_API_KEY",
}


@pytest.fixture
def keys(monkeypatch):
    """Set provider keys (on settings and in the env the components read) by short name."""

    def set_keys(**values):
        for field, env in KEYS.items():
            value = values.get(field.removesuffix("_api_key"), "")
            monkeypatch.setattr(settings, field, value)
            monkeypatch.setenv(env, value or "unset")

    monkeypatch.setattr(settings, "llm_provider", "auto")
    monkeypatch.setattr(settings, "embedding_provider", "auto")
    monkeypatch.setattr(settings, "chat_model", "")
    return set_keys


def echo_llm() -> MockChatGenerator:
    return MockChatGenerator(response_fn=lambda messages: messages[-1].text)


@pytest.mark.parametrize(
    ("set_keys", "provider"),
    [
        ({"anthropic": "sk-ant", "openai": "sk-oa"}, "anthropic"),
        ({"openai": "sk-oa", "google": "g"}, "openai"),
        ({"google": "g"}, "gemini"),
        ({}, "none"),
    ],
)
def test_auto_picks_provider_from_keys(keys, set_keys, provider):
    keys(**set_keys)
    assert settings.llm_provider_resolved == provider


def test_explicit_provider_wins(keys, monkeypatch):
    keys(anthropic="sk-ant", openai="sk-oa")
    monkeypatch.setattr(settings, "llm_provider", "openai")
    assert settings.llm_provider_resolved == "openai"


@pytest.mark.parametrize("provider", ["anthropic", "openai", "gemini"])
def test_each_provider_builds_a_chat_pipeline(keys, provider):
    keys(**{provider if provider != "gemini" else "google": "test-key"})
    llm = providers.chat_generator()
    assert llm is not None
    assert providers.chat_model_name(llm)  # shown in /api/health
    pipeline = build_chat_pipeline(llm)
    assert {"prompt_builder", "llm"} <= set(pipeline.graph.nodes)


def test_no_key_means_no_llm(keys):
    keys()
    assert providers.chat_generator() is None


def test_anthropic_defaults(keys):
    keys(anthropic="sk-ant")
    llm = providers.chat_generator()
    assert isinstance(llm, providers.ClaudeChatGenerator)
    assert llm.model == "claude-opus-5-5"
    kwargs = llm.generation_kwargs
    assert kwargs["max_tokens"] == 16_000
    assert kwargs["output_config"] == {"effort": "medium"}
    assert kwargs["extra_body"] == {"fallbacks": "default"}
    assert kwargs["extra_headers"] == {"anthropic-beta": "server-side-fallback-2026-07-01"}


def test_anthropic_request_carries_fallbacks(keys):
    """extra_body must survive Haystack's parameter filter and reach the SDK call."""
    keys(anthropic="sk-ant")
    llm = providers.chat_generator()
    sent = {}

    async def fake_create(**kwargs):
        sent.update(kwargs)
        raise RuntimeError("stop before the network")

    async def call():
        await llm.warm_up_async()  # creates the SDK client (pipelines do this on first run)
        llm.async_client.messages.create = fake_create
        await llm.run_async(messages=[ChatMessage.from_user("hi")])

    with pytest.raises(RuntimeError, match="stop before the network"):
        asyncio.run(call())
    assert sent["model"] == "claude-opus-5-5"
    assert sent["extra_body"] == {"fallbacks": "default"}
    assert sent["max_tokens"] == 16_000
    assert "temperature" not in sent  # rejected by current Claude models


def test_other_claude_models_skip_fallback_params(keys, monkeypatch):
    keys(anthropic="sk-ant")
    monkeypatch.setattr(settings, "chat_model", "claude-haiku-4-5")
    llm = providers.chat_generator()
    assert llm.model == "claude-haiku-4-5"
    assert llm.generation_kwargs == {"max_tokens": 16_000}


def test_chat_model_override(keys, monkeypatch):
    keys(openai="sk-oa")
    monkeypatch.setattr(settings, "chat_model", "my-model")
    assert providers.chat_generator().model == "my-model"


@pytest.mark.parametrize(
    ("set_keys", "embedder"),
    [({"openai": "k"}, "OpenAITextEmbedder"), ({"google": "k"}, "GoogleGenAITextEmbedder")],
)
def test_embeddings_follow_keys(keys, set_keys, embedder):
    keys(**set_keys)
    assert type(providers.text_embedder("query")).__name__ == embedder


def test_anthropic_alone_uses_hash_embeddings(keys):
    # Anthropic has no embeddings API.
    keys(anthropic="sk-ant")
    assert isinstance(providers.text_embedder("document"), HashTextEmbedder)


def test_gemini_embeddings_are_1536_dims(keys):
    keys(google="k")
    embedder = providers.text_embedder("query")
    assert embedder._config["output_dimensionality"] == EMBEDDING_DIM
    assert embedder._config["task_type"] == "RETRIEVAL_QUERY"


def test_empty_base_url_env_is_dropped(monkeypatch):
    # An empty OPENAI_BASE_URL= line in .env would otherwise break the OpenAI client.
    monkeypatch.setenv("OPENAI_BASE_URL", "")
    importlib.reload(config)
    assert "OPENAI_BASE_URL" not in os.environ


def test_chat_pipeline_sends_the_message():
    pipeline = build_chat_pipeline(echo_llm())
    result = asyncio.run(pipeline.run_async({"prompt_builder": {"message": "ping"}}))
    assert result["llm"]["replies"][0].text == "ping"


def test_langfuse_connector_added_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "langfuse_public_key", "pk-lf-test")
    monkeypatch.setattr(settings, "langfuse_secret_key", "sk-lf-test")
    monkeypatch.setattr(tracing.tracer, "is_content_tracing_enabled", False)
    # setenv first so monkeypatch also removes the value the code sets.
    monkeypatch.setenv("HAYSTACK_LANGFUSE_ENFORCE_FLUSH", "true")
    monkeypatch.delenv("HAYSTACK_LANGFUSE_ENFORCE_FLUSH")

    pipeline = build_chat_pipeline(echo_llm())

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


def test_chat_works_when_langfuse_rejects_keys(monkeypatch, langfuse_rejecting_keys):
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

    pipeline = build_chat_pipeline(echo_llm())
    result = asyncio.run(pipeline.run_async({"prompt_builder": {"message": "q"}}))

    assert result["llm"]["replies"][0].text == "q"
    assert result["tracer"]["trace_url"] == ""


# --- /api/playground/chat


@pytest.fixture
def signed_in():
    app.dependency_overrides[current_user] = lambda: User(id=uuid.uuid4())
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def with_pipeline(client):
    """Swap the app's chat pipeline for one with the given LLM component."""
    original = client.app.state.chat_pipeline

    def use(llm):
        client.app.state.chat_pipeline = build_chat_pipeline(llm)

    yield use
    client.app.state.chat_pipeline = original


def test_chat_requires_sign_in(client):
    assert client.post("/api/playground/chat", json={"message": "hi"}).status_code == 401


def test_chat_without_llm_is_503(client, signed_in):
    client.app.state.chat_pipeline = None
    res = client.post("/api/playground/chat", json={"message": "hi"})
    assert res.status_code == 503
    assert "No LLM configured" in res.json()["detail"]


def test_chat_returns_the_reply(client, signed_in, with_pipeline):
    with_pipeline(echo_llm())
    res = client.post("/api/playground/chat", json={"message": "hello there"})
    assert res.status_code == 200, res.text
    assert res.json()["reply"] == "hello there"


@component
class RefusingLLM:
    @component.output_types(replies=list[ChatMessage])
    def run(self, messages: list[ChatMessage]) -> dict:
        reply = ChatMessage.from_assistant("", meta={"finish_reason": "content_filter"})
        return {"replies": [reply]}


def test_chat_explains_a_refusal(client, signed_in, with_pipeline):
    with_pipeline(RefusingLLM())
    res = client.post("/api/playground/chat", json={"message": "x"})
    assert res.json()["reply"] == "The model declined to answer this request."


@component
class FailingLLM:
    @component.output_types(replies=list[ChatMessage])
    def run(self, messages: list[ChatMessage]) -> dict:
        raise ValueError("invalid x-api-key")


def test_provider_errors_are_502_with_the_reason(client, signed_in, with_pipeline):
    with_pipeline(FailingLLM())
    res = client.post("/api/playground/chat", json={"message": "x"})
    assert res.status_code == 502
    assert "llm failed" in res.json()["detail"] and "invalid x-api-key" in res.json()["detail"]
