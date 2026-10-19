import hashlib
import math
import re

# Must match the vector(...) column size in supabase/migrations.
EMBEDDING_DIM = 1536


async def embed(text: str) -> list[float]:
    """Placeholder embedding: a feature-hashed bag of words, L2-normalised.

    Texts that share words score as similar, which is enough to demo vector
    search without an API key. Replace the body with a real embedding model
    and keep EMBEDDING_DIM in sync with the migration.
    """
    vec = [0.0] * EMBEDDING_DIM
    for token in re.findall(r"\w+", text.lower()):
        h = int.from_bytes(hashlib.blake2b(token.encode(), digest_size=8).digest())
        vec[h % EMBEDDING_DIM] += 1.0 if (h >> 32) & 1 else -1.0
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        # Cosine distance to a zero vector is NaN, so give empty texts a direction.
        vec[0], norm = 1.0, 1.0
    return [v / norm for v in vec]
