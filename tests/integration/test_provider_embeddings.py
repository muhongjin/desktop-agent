from __future__ import annotations

import json
from collections.abc import Sequence

import httpx
import pytest

from desktop_agent.knowledge.embedding import EmbeddingError, OpenAICompatibleEmbedding
from desktop_agent.providers.openai_compatible import (
    OpenAICompatibleClient,
    ProviderError,
)


@pytest.mark.asyncio
async def test_embed_texts_sends_payload_and_sorts_by_index():
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.url.path.endswith("/embeddings")
        assert payload["model"] == "bge-m3"
        assert payload["input"] == ["甲", "乙"]
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.0, 1.0]},
                    {"index": 0, "embedding": [1.0, 0.0]},
                ]
            },
        )

    client = OpenAICompatibleClient(
        "https://example.test/v1",
        "secret",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    try:
        vectors = await client.embed_texts(model_id="bge-m3", texts=["甲", "乙"])
    finally:
        await client.client.aclose()
    assert vectors == [[1.0, 0.0], [0.0, 1.0]]


@pytest.mark.asyncio
async def test_embed_texts_rejects_short_payload():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0]}]})

    client = OpenAICompatibleClient(
        "https://example.test/v1",
        "secret",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    try:
        with pytest.raises(ProviderError):
            await client.embed_texts(model_id="model", texts=["甲", "乙"])
    finally:
        await client.client.aclose()


@pytest.mark.asyncio
async def test_embedding_retries_retryable_errors():
    class FlakyClient:
        def __init__(self):
            self.attempts = 0

        async def embed_texts(self, *, model_id: str, texts: Sequence[str]):
            self.attempts += 1
            if self.attempts == 1:
                raise ProviderError("rate limited", retryable=True, status_code=429)
            return [[1.0, 0.0] for _ in texts]

    client = FlakyClient()

    async def factory():
        return client

    embedding = OpenAICompatibleEmbedding(factory, "model", retry_delay=0)
    vectors = await embedding.embed(["文本"])
    assert client.attempts == 2
    assert vectors == [[1.0, 0.0]]


@pytest.mark.asyncio
async def test_embedding_stops_after_max_attempts():
    class BrokenClient:
        async def embed_texts(self, *, model_id: str, texts: Sequence[str]):
            raise ProviderError("bad request", retryable=False, status_code=400)

    async def factory():
        return BrokenClient()

    embedding = OpenAICompatibleEmbedding(factory, "model", retry_delay=0)
    with pytest.raises(EmbeddingError):
        await embedding.embed(["文本"])


@pytest.mark.asyncio
async def test_probe_dimension():
    class FixedClient:
        async def embed_texts(self, *, model_id: str, texts: Sequence[str]):
            return [[0.1, 0.2, 0.3] for _ in texts]

    async def factory():
        return FixedClient()

    embedding = OpenAICompatibleEmbedding(factory, "model")
    assert await embedding.probe_dimension() == 3
