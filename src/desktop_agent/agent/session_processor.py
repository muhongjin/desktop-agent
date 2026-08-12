from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from desktop_agent.domain.models import MessageStatus
from desktop_agent.providers.openai_compatible import (
    AssistantTurn,
    OpenAICompatibleClient,
    ProviderError,
    TextDelta,
)

from .session_retry import SessionRetry


class SessionStopped(Exception):
    pass


@dataclass(frozen=True, slots=True)
class AgentEvent:
    type: str
    data: dict[str, Any]


@dataclass(frozen=True, slots=True)
class SessionProcessResult:
    content: str
    turn: AssistantTurn


class SessionProcessor:
    PERSIST_CHAR_THRESHOLD = 128
    PERSIST_INTERVAL = 0.1

    def __init__(
        self,
        repository,
        provider: OpenAICompatibleClient,
        retry: SessionRetry | None = None,
    ):
        self.repository = repository
        self.provider = provider
        self.retry = retry or SessionRetry()

    async def process(
        self,
        *,
        session_id: str,
        draft_id: str,
        model_id: str,
        messages,
        thinking_strength: str | None,
        tools,
        request_params: dict[str, Any] | None,
        stop_event: asyncio.Event | None,
    ) -> AsyncIterator[AgentEvent]:
        attempt = 1
        best_partial = ""
        while True:
            accumulated = ""
            pending_chars = 0
            final_turn = None
            last_persist = asyncio.get_running_loop().time()
            try:
                stream = self.provider.stream_chat(
                    model_id=model_id,
                    messages=messages,
                    thinking_strength=thinking_strength,
                    tools=tools,
                    request_params=request_params,
                    conversation_id=session_id,
                )
                async for event in self._stream_until_stopped(stream, stop_event):
                    if isinstance(event, TextDelta):
                        accumulated += event.text
                        pending_chars += len(event.text)
                        now = asyncio.get_running_loop().time()
                        if (
                            pending_chars >= self.PERSIST_CHAR_THRESHOLD
                            or now - last_persist >= self.PERSIST_INTERVAL
                        ):
                            self._persist_partial(draft_id, accumulated)
                            last_persist = now
                            pending_chars = 0
                        yield AgentEvent(
                            "text_delta",
                            {
                                "message_id": draft_id,
                                "text": event.text,
                                "content": accumulated,
                            },
                        )
                    elif isinstance(event, AssistantTurn):
                        final_turn = event
                if final_turn is None:
                    raise ProviderError(
                        "Provider stream ended unexpectedly", retryable=True
                    )
                if not accumulated and final_turn.text:
                    accumulated = final_turn.text
                    yield AgentEvent(
                        "text_delta",
                        {
                            "message_id": draft_id,
                            "text": final_turn.text,
                            "content": accumulated,
                        },
                    )
                self._persist_partial(draft_id, accumulated)
                yield AgentEvent(
                    "processor_finished",
                    {"result": SessionProcessResult(accumulated, final_turn)},
                )
                return
            except SessionStopped:
                content = self._best_partial(best_partial, accumulated)
                self.repository.update_message(
                    draft_id,
                    content,
                    MessageStatus.STOPPED,
                    completion_marker=True,
                )
                yield AgentEvent("turn_stopped", {"message_id": draft_id})
                return
            except ProviderError as error:
                best_partial = self._best_partial(best_partial, accumulated)
                if best_partial:
                    self._persist_partial(draft_id, best_partial)
                decision = self.retry.classify(error)
                if decision.retryable and attempt < self.retry.MAX_ATTEMPTS:
                    attempt += 1
                    retry_count = attempt - 1
                    delay = self.retry.delay(retry_count, error)
                    yield AgentEvent(
                        "retrying",
                        {
                            "message_id": draft_id,
                            "attempt": attempt,
                            "max_attempts": self.retry.MAX_ATTEMPTS,
                            "retry_count": retry_count,
                            "delay": delay,
                            "error": decision.message,
                        },
                    )
                    if await self.retry.wait(delay, stop_event):
                        continue
                    self.repository.update_message(
                        draft_id,
                        best_partial,
                        MessageStatus.STOPPED,
                        completion_marker=True,
                    )
                    yield AgentEvent("turn_stopped", {"message_id": draft_id})
                    return
                visible_error = (
                    f"{best_partial}\n\n错误：{decision.message}"
                    if best_partial
                    else f"错误：{decision.message}"
                )
                self.repository.update_message(
                    draft_id,
                    visible_error,
                    MessageStatus.STOPPED,
                    completion_marker=True,
                )
                yield AgentEvent(
                    "turn_stopped",
                    {
                        "message_id": draft_id,
                        "error": decision.message,
                        "context_overflow": decision.context_overflow,
                    },
                )
                return

    def _persist_partial(self, draft_id: str, content: str) -> None:
        self.repository.update_message(
            draft_id,
            content,
            MessageStatus.STOPPED,
            completion_marker=False,
        )

    @staticmethod
    def _best_partial(previous: str, current: str) -> str:
        return current if len(current) >= len(previous) else previous

    async def _stream_until_stopped(self, stream, stop_event: asyncio.Event | None):
        iterator = stream.__aiter__()
        while True:
            next_event = asyncio.create_task(iterator.__anext__())
            stop_waiter = asyncio.create_task(stop_event.wait()) if stop_event is not None else None
            try:
                if stop_waiter is None:
                    yield await next_event
                    continue
                done, _ = await asyncio.wait(
                    {next_event, stop_waiter}, return_when=asyncio.FIRST_COMPLETED
                )
                if stop_waiter in done and stop_event.is_set():
                    if not next_event.done():
                        next_event.cancel()
                        with suppress(asyncio.CancelledError):
                            await next_event
                    with suppress(asyncio.CancelledError, RuntimeError):
                        await iterator.aclose()
                    raise SessionStopped
                yield next_event.result()
            except StopAsyncIteration:
                return
            finally:
                if stop_waiter is not None:
                    stop_waiter.cancel()
