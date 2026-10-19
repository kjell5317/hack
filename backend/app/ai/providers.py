"""Pick Haystack components for the configured LLM provider.

Both providers embed into 1536 dimensions so the same vector column works.
Vectors from different models aren't comparable, though: after switching
LLM_PROVIDER, re-embed existing notes (or start with an empty table).
"""

from typing import Any, Literal

from haystack.components.embedders import OpenAITextEmbedder
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack_integrations.components.embedders.google_genai import GoogleGenAITextEmbedder
from haystack_integrations.components.generators.google_genai import GoogleGenAIChatGenerator

from app.ai.components import EMBEDDING_DIM, HashTextEmbedder
from app.config import settings

Purpose = Literal["query", "document"]


def text_embedder(purpose: Purpose) -> Any:
    match settings.llm_provider:
        case "openai":
            return OpenAITextEmbedder(model="text-embedding-3-small", dimensions=EMBEDDING_DIM)
        case "gemini":
            task = "RETRIEVAL_QUERY" if purpose == "query" else "RETRIEVAL_DOCUMENT"
            return GoogleGenAITextEmbedder(
                model="gemini-embedding-001",
                config={"output_dimensionality": EMBEDDING_DIM, "task_type": task},
            )
        case "none":
            return HashTextEmbedder()


def chat_generator() -> Any | None:
    kwargs = {"model": settings.chat_model} if settings.chat_model else {}
    match settings.llm_provider:
        case "openai":
            return OpenAIChatGenerator(**kwargs)
        case "gemini":
            return GoogleGenAIChatGenerator(**kwargs)
        case "none":
            return None
