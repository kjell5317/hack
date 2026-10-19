from functools import cache

from app.ai.providers import Purpose, text_embedder


@cache
def _embedder(purpose: Purpose):
    embedder = text_embedder(purpose)
    if hasattr(embedder, "warm_up"):
        embedder.warm_up()
    return embedder


async def embed(text: str, purpose: Purpose = "document") -> list[float]:
    """Embed text with the configured provider.

    Use purpose="query" for search input: Gemini embeds queries and documents
    differently for better retrieval (OpenAI ignores it).
    """
    result = await _embedder(purpose).run_async(text=text)
    return result["embedding"]
