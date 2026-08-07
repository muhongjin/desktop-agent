import json
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any

import httpx


class ProviderError(Exception):
    pass


class ModelDiscoveryError(ProviderError):
    pass


class ProviderTimeout(ProviderError):
    pass


@dataclass(frozen=True, slots=True)
class TextDelta:
    text: str


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass(frozen=True, slots=True)
class AssistantTurn:
    text: str
    tool_calls: tuple[ToolCall, ...]
    finish_reason: str | None


StreamEvent = TextDelta | AssistantTurn


class OpenAICompatibleClient:
    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(timeout=timeout)

    @property
    def headers(self) -> dict[str, str]:
        if not self.api_key:
            return {}
        return {"Authorization": f"Bearer {self.api_key}"}

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def discover_models(self) -> list[str]:
        try:
            response = await self.client.get(f"{self.base_url}/models", headers=self.headers)
            response.raise_for_status()
            payload = response.json()
            models = payload.get("data", [])
            return [item["id"] for item in models if isinstance(item, dict) and isinstance(item.get("id"), str)]
        except httpx.TimeoutException as error:
            raise ModelDiscoveryError("Model discovery timed out; enter a model ID manually") from error
        except (httpx.HTTPError, ValueError, TypeError) as error:
            detail = self._safe_error("Model discovery failed", error)
            raise ModelDiscoveryError(f"{detail}; enter a model ID manually") from error

    async def stream_chat(
        self,
        *,
        model_id: str,
        messages: Sequence[dict[str, Any]],
        thinking_strength: str | None = None,
        tools: Sequence[dict[str, Any]] | None = None,
        request_params: dict[str, Any] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        payload: dict[str, Any] = {
            "model": model_id,
            "messages": list(messages),
            "stream": True,
        }
        if thinking_strength:
            payload["reasoning_effort"] = thinking_strength
        if tools:
            payload["tools"] = list(tools)
        payload.update(request_params or {})
        text_parts: list[str] = []
        calls: dict[int, dict[str, str]] = {}
        finish_reason = None
        try:
            async with self.client.stream(
                "POST", f"{self.base_url}/chat/completions", headers=self.headers, json=payload
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data or data == "[DONE]":
                        continue
                    chunk = json.loads(data)
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    choice = choices[0]
                    finish_reason = choice.get("finish_reason") or finish_reason
                    delta = choice.get("delta") or {}
                    content = delta.get("content")
                    if isinstance(content, str) and content:
                        text_parts.append(content)
                        yield TextDelta(content)
                    for fragment in delta.get("tool_calls") or []:
                        index = int(fragment.get("index", 0))
                        current = calls.setdefault(index, {"id": "", "name": "", "arguments": ""})
                        if fragment.get("id"):
                            current["id"] = fragment["id"]
                        function = fragment.get("function") or {}
                        if function.get("name"):
                            current["name"] += function["name"]
                        if function.get("arguments"):
                            current["arguments"] += function["arguments"]
        except httpx.TimeoutException as error:
            raise ProviderTimeout("Provider request timed out") from error
        except httpx.HTTPStatusError as error:
            raise ProviderError(self._safe_error("Provider request failed", error)) from error
        except (httpx.HTTPError, json.JSONDecodeError, TypeError, ValueError) as error:
            raise ProviderError(self._safe_error("Invalid provider response", error)) from error
        tool_calls = tuple(ToolCall(value["id"], value["name"], value["arguments"]) for _, value in sorted(calls.items()))
        yield AssistantTurn("".join(text_parts), tool_calls, finish_reason)

    def _safe_error(self, prefix: str, error: Exception) -> str:
        detail = str(error)
        if self.api_key:
            detail = detail.replace(self.api_key, "[redacted]")
        return f"{prefix}: {detail}"
