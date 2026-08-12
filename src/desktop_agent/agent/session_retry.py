from __future__ import annotations

import asyncio
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from desktop_agent.providers.openai_compatible import ProviderError

RETRYABLE_MESSAGE_PATTERNS = (
    re.compile(r"429|500|502|503|504|524", re.IGNORECASE),
    re.compile(
        r"rate increased too quickly|rate limit|rate-limit|rate_limit|too many requests",
        re.IGNORECASE,
    ),
    re.compile(
        r"overloaded|service unavailable|service_unavailable|service-unavailable|"
        r"internal error|internal_error|internal server error|server error|server_error|"
        r"server-error|provider returned error|provider_returned_error|provider-returned-error",
        re.IGNORECASE,
    ),
    re.compile(
        r"terminated|fetch failed|failed to fetch|network error|upstream connect|"
        r"connection error|connection refused|connection lost|socket connection was closed|"
        r"socket hang up|reset before headers|getaddrinfo|enotfound|eai_again|econnrefused|"
        r"econnreset|etimedout",
        re.IGNORECASE,
    ),
    re.compile(
        r"^timeout$|\b(?:request|response|connection|network|stream|read) "
        r"(?:timeout|timed out|time out)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"try your request again|retry your request|resource exhausted|resource_exhausted",
        re.IGNORECASE,
    ),
)

CONTEXT_OVERFLOW_PATTERNS = (
    re.compile(r"context.{0,30}(length|window|limit|size)", re.IGNORECASE),
    re.compile(
        r"(maximum|max).{0,30}(context|prompt|input).{0,30}(token|length|size)",
        re.IGNORECASE,
    ),
    re.compile(r"(prompt|input).{0,30}(too long|too large|exceed|超过)", re.IGNORECASE),
    re.compile(r"too many tokens|token limit", re.IGNORECASE),
    re.compile(r"上下文.{0,20}(超|限制|过长)"),
)


@dataclass(frozen=True, slots=True)
class RetryDecision:
    message: str
    retryable: bool
    context_overflow: bool


class SessionRetry:
    MAX_ATTEMPTS = 5
    RETRY_INITIAL_DELAY = 2.0
    RETRY_BACKOFF_FACTOR = 2.0
    RETRY_MAX_DELAY_NO_HEADERS = 30.0
    RETRY_MAX_DELAY = 2_147_483.647

    def __init__(self, delays: tuple[float, ...] | None = None):
        self.delays = delays

    def classify(self, error: ProviderError) -> RetryDecision:
        message = self.format_error(error)
        combined = " ".join(
            value for value in (str(error), error.response_body or "") if value
        )
        context_overflow = any(
            pattern.search(combined) for pattern in CONTEXT_OVERFLOW_PATTERNS
        ) or error.status_code == 413
        if context_overflow:
            return RetryDecision(message, False, True)
        retryable = (
            error.retryable
            or (error.status_code is not None and error.status_code >= 500)
            or any(pattern.search(combined) for pattern in RETRYABLE_MESSAGE_PATTERNS)
        )
        return RetryDecision(message, retryable, False)

    @staticmethod
    def format_error(error: ProviderError) -> str:
        message = str(error).strip() or error.__class__.__name__
        lower = message.lower()
        if "too_many_requests" in lower:
            return "Too Many Requests"
        if (
            "overloaded" in lower
            or "exhausted" in lower
            or "unavailable" in lower
        ):
            return "Provider is overloaded"
        return message

    def delay(self, retry_count: int, error: ProviderError) -> float:
        if self.delays:
            index = min(max(retry_count - 1, 0), len(self.delays) - 1)
            return max(0.0, self.delays[index])
        headers = self._headers(error.response_headers)
        retry_after_ms = self._number(headers.get("retry-after-ms"))
        if retry_after_ms is not None:
            return self._cap(retry_after_ms / 1000)
        retry_after = headers.get("retry-after")
        if retry_after:
            seconds = self._number(retry_after)
            if seconds is not None:
                return self._cap(math.ceil(seconds * 1000) / 1000)
            try:
                target = parsedate_to_datetime(retry_after)
                if target.tzinfo is None:
                    target = target.replace(tzinfo=UTC)
                remaining = (target - datetime.now(UTC)).total_seconds()
                if remaining > 0:
                    return self._cap(math.ceil(remaining * 1000) / 1000)
            except (TypeError, ValueError, OverflowError):
                pass
        exponential = self.RETRY_INITIAL_DELAY * self.RETRY_BACKOFF_FACTOR ** (
            max(retry_count, 1) - 1
        )
        if headers:
            return self._cap(exponential)
        return min(self._cap(exponential), self.RETRY_MAX_DELAY_NO_HEADERS)

    @staticmethod
    async def wait(delay: float, stop_event: asyncio.Event | None) -> bool:
        if stop_event is not None and stop_event.is_set():
            return False
        if delay <= 0:
            return True
        if stop_event is None:
            await asyncio.sleep(delay)
            return True
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=delay)
        except TimeoutError:
            return True
        return False

    @classmethod
    def _cap(cls, seconds: float) -> float:
        return min(max(0.0, seconds), cls.RETRY_MAX_DELAY)

    @staticmethod
    def _headers(headers: Mapping[str, str] | None) -> dict[str, str]:
        if not headers:
            return {}
        return {str(key).lower(): str(value) for key, value in headers.items()}

    @staticmethod
    def _number(value: str | None) -> float | None:
        if value is None:
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed >= 0 else None
