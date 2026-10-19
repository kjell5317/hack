import asyncio
import math

from app.embeddings import EMBEDDING_DIM, embed


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_embedding_shape_and_norm():
    vec = asyncio.run(embed("hello world"))
    assert len(vec) == EMBEDDING_DIM
    assert math.isclose(math.sqrt(sum(v * v for v in vec)), 1.0)


def test_similar_texts_score_higher():
    cat, cat2, soup = (
        asyncio.run(embed(t))
        for t in ["the cat sat on the mat", "where is the cat", "tomato soup recipe"]
    )
    assert cosine(cat, cat2) > cosine(cat, soup)


def test_empty_text_is_not_a_zero_vector():
    assert any(asyncio.run(embed("!!!")))
