"""Haystack components for the configured LLM provider.

Build LLM features from chat_generator() and text_embedder() so that switching
provider (LLM_PROVIDER / which API key is set) keeps working. Embeddings are
1536-dimensional for every provider so one vector(1536) column fits all; vectors
from different models aren't comparable, though, so re-embed after switching.
"""

from typing import Any, ClassVar, Literal

from haystack import component
from haystack.components.embedders import OpenAITextEmbedder
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack_integrations.components.embedders.google_genai import GoogleGenAITextEmbedder
from haystack_integrations.components.generators.anthropic import AnthropicChatGenerator
from haystack_integrations.components.generators.google_genai import GoogleGenAIChatGenerator

from app.core.ai.hash_embedder import EMBEDDING_DIM, HashTextEmbedder
from app.core.config import settings

Purpose = Literal["query", "document"]

DEFAULT_ANTHROPIC_MODEL = "claude-opus-5-5"

# Models that take `output_config.effort` and the server-side `fallbacks` parameter.
_CURRENT_CLAUDE_MODELS = {
    "claude-fable-5-2",
    "claude-fable-5-1",
    "claude-opus-5-5",
    "claude-opus-5",
    "claude-sonnet-5-5",
}


@component
class ClaudeChatGenerator(AnthropicChatGenerator):
    """AnthropicChatGenerator that may also send `extra_body`.

    Needed for the server-side `fallbacks` parameter, which the Haystack
    integration doesn't pass through yet.
    """

    ALLOWED_PARAMS: ClassVar[list[str]] = [*AnthropicChatGenerator.ALLOWED_PARAMS, "extra_body"]


def anthropic_generation_kwargs(model: str) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"max_tokens": 16_000}
    if model in _CURRENT_CLAUDE_MODELS:
        # Opus 5.5 defaults to medium effort; stated here so it's easy to tune
        # (low for quick chat, high/xhigh for hard reasoning).
        kwargs["output_config"] = {"effort": "medium"}
        # If Claude declines a request (stop_reason "refusal"), the API re-runs
        # it on Anthropic's recommended fallback model instead of returning nothing.
        kwargs["extra_headers"] = {"anthropic-beta": "server-side-fallback-2026-07-01"}
        kwargs["extra_body"] = {"fallbacks": "default"}
    return kwargs


def chat_generator() -> Any | None:
    """Chat component for the configured provider, or None without one."""
    model = settings.chat_model
    match settings.llm_provider_resolved:
        case "anthropic":
            model = model or DEFAULT_ANTHROPIC_MODEL
            return ClaudeChatGenerator(
                model=model, generation_kwargs=anthropic_generation_kwargs(model)
            )
        case "openai":
            # OPENAI_BASE_URL points this at any OpenAI-compatible partner API.
            return OpenAIChatGenerator(**({"model": model} if model else {}))
        case "gemini":
            return GoogleGenAIChatGenerator(**({"model": model} if model else {}))
        case "none":
            return None


def chat_model_name(generator: Any | None) -> str | None:
    # The Gemini component keeps it in `_model`.
    return getattr(generator, "model", None) or getattr(generator, "_model", None)


def text_embedder(purpose: Purpose) -> Any:
    match settings.embedding_provider_resolved:
        case "openai":
            return OpenAITextEmbedder(model="text-embedding-3-small", dimensions=EMBEDDING_DIM)
        case "gemini":
            task = "RETRIEVAL_QUERY" if purpose == "query" else "RETRIEVAL_DOCUMENT"
            return GoogleGenAITextEmbedder(
                model="gemini-embedding-001",
                config={"output_dimensionality": EMBEDDING_DIM, "task_type": task},
            )
        case "hash":
            return HashTextEmbedder()
