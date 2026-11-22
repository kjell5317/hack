import hashlib
import math
import re

from haystack import component

# Every provider embeds into this many dimensions: store embeddings in vector(1536) columns.
EMBEDDING_DIM = 1536


def hash_embedding(text: str) -> list[float]:
    """Feature-hashed bag of words, L2-normalised. Texts sharing words score as similar."""
    vec = [0.0] * EMBEDDING_DIM
    for token in re.findall(r"\w+", text.lower()):
        h = int.from_bytes(hashlib.blake2b(token.encode(), digest_size=8).digest())
        vec[h % EMBEDDING_DIM] += 1.0 if (h >> 32) & 1 else -1.0
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        # Cosine distance to a zero vector is NaN, so give empty texts a direction.
        vec[0], norm = 1.0, 1.0
    return [v / norm for v in vec]


@component
class HashTextEmbedder:
    """Stand-in for a real embedding model when LLM_PROVIDER=none (no API key needed)."""

    @component.output_types(embedding=list[float])
    def run(self, text: str) -> dict[str, list[float]]:
        return {"embedding": hash_embedding(text)}

    @component.output_types(embedding=list[float])
    async def run_async(self, text: str) -> dict[str, list[float]]:
        return self.run(text)
