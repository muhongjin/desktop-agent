from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import Protocol

from desktop_agent.providers.openai_compatible import (
    OpenAICompatibleClient,
    ProviderError,
)


class EmbeddingError(Exception):
    pass


class EmbeddingClient(Protocol):
    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


ClientFactory = Callable[[], Awaitable[OpenAICompatibleClient]]


class OpenAICompatibleEmbedding:
    def __init__(
        self,
        client_factory: ClientFactory,
        model_id: str,
        *,
        batch_size: int = 32,
        max_attempts: int = 3,
        retry_delay: float = 0.5,
    ):
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        self.client_factory = client_factory
        self.model_id = model_id
        self.batch_size = batch_size
        self.max_attempts = max(1, max_attempts)
        self.retry_delay = retry_delay

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        items = list(texts)
        if not items:
            return []
        client = await self.client_factory()
        vectors: list[list[float]] = []
        for start in range(0, len(items), self.batch_size):
            batch = items[start : start + self.batch_size]
            vectors.extend(await self._embed_batch(client, batch))
        return vectors

    async def probe_dimension(self, sample: str = "dimension probe") -> int:
        vectors = await self.embed([sample])
        if not vectors or not vectors[0]:
            raise EmbeddingError("嵌入服务返回了空向量")
        return len(vectors[0])

    async def _embed_batch(
        self, client: OpenAICompatibleClient, batch: list[str]
    ) -> list[list[float]]:
        last_error: ProviderError | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                return await client.embed_texts(model_id=self.model_id, texts=batch)
            except ProviderError as error:
                last_error = error
                if not error.retryable or attempt == self.max_attempts:
                    break
                await asyncio.sleep(self.retry_delay * attempt)
        raise EmbeddingError(f"嵌入请求失败：{last_error}") from last_error
