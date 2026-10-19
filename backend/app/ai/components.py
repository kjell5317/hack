import hashlib
import math
import re

from haystack import Document, component
from supabase import AsyncClient

# Must match the vector(...) column size in supabase/migrations.
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


@component
class SupabaseNoteRetriever:
    """Finds a user's notes closest to an embedding via the match_notes SQL function."""

    def __init__(self, supabase: AsyncClient, top_k: int = 5) -> None:
        self.supabase = supabase
        self.top_k = top_k

    @component.output_types(documents=list[Document])
    def run(self, query_embedding: list[float], user_id: str) -> dict[str, list[Document]]:
        raise NotImplementedError("Uses the async Supabase client: run the pipeline with run_async")

    @component.output_types(documents=list[Document])
    async def run_async(
        self, query_embedding: list[float], user_id: str
    ) -> dict[str, list[Document]]:
        params = {
            "query_embedding": query_embedding,
            "match_user_id": user_id,
            "match_count": self.top_k,
        }
        res = await self.supabase.rpc("match_notes", params).execute()
        documents = [
            Document(
                id=str(row["id"]),
                content=row["content"],
                score=row["similarity"],
                meta={"created_at": row["created_at"]},
            )
            for row in res.data
        ]
        return {"documents": documents}
