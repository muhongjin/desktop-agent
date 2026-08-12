import json
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx


class ProviderError(Exception):
    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        status_code: int | None = None,
        response_headers: Mapping[str, str] | None = None,
        response_body: str | None = None,
    ):
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code
        self.response_headers = dict(response_headers or {})
        self.response_body = response_body


class ModelDiscoveryError(ProviderError):
    pass


class ProviderTimeout(ProviderError):
    def __init__(self, message: str):
        super().__init__(message, retryable=True)


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
        timeout: float = 120.0,
        api_protocol: str = "chat_completions",
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.api_protocol = api_protocol
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(
            timeout=timeout,
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
                keepalive_expiry=300,
            ),
        )

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
            return [
                item["id"]
                for item in models
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            ]
        except httpx.TimeoutException as error:
            raise ModelDiscoveryError(
                "Model discovery timed out; enter a model ID manually"
            ) from error
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
        conversation_id: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        try:
            if self.api_protocol == "responses":
                stream = self._stream_responses(
                    model_id=model_id,
                    messages=messages,
                    thinking_strength=thinking_strength,
                    tools=tools,
                    request_params=request_params,
                    conversation_id=conversation_id,
                )
            else:
                stream = self._stream_chat_completions(
                    model_id=model_id,
                    messages=messages,
                    thinking_strength=thinking_strength,
                    tools=tools,
                    request_params=request_params,
                )
            async for event in stream:
                yield event
        except httpx.TimeoutException as error:
            raise ProviderTimeout("Provider request timed out") from error
        except httpx.HTTPStatusError as error:
            status_code = error.response.status_code
            raise ProviderError(
                self._safe_error("Provider request failed", error),
                retryable=self._retryable_status(status_code),
                status_code=status_code,
                response_headers=dict(error.response.headers),
                response_body=self._safe_response_body(error.response),
            ) from error
        except httpx.HTTPError as error:
            raise ProviderError(
                self._safe_error("Provider connection failed", error), retryable=True
            ) from error
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            raise ProviderError(
                self._safe_error("Invalid provider response", error), retryable=True
            ) from error

    async def _stream_chat_completions(
        self,
        *,
        model_id: str,
        messages: Sequence[dict[str, Any]],
        thinking_strength: str | None,
        tools: Sequence[dict[str, Any]] | None,
        request_params: dict[str, Any] | None,
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
        async with self.client.stream(
            "POST", f"{self.base_url}/chat/completions", headers=self.headers, json=payload
        ) as response:
            if response.is_error:
                await response.aread()
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
                    current = calls.setdefault(
                        index, {"id": "", "name": "", "arguments": ""}
                    )
                    if fragment.get("id"):
                        current["id"] = fragment["id"]
                    function = fragment.get("function") or {}
                    if function.get("name"):
                        current["name"] += function["name"]
                    if function.get("arguments"):
                        current["arguments"] += function["arguments"]
        tool_calls = tuple(
            ToolCall(value["id"], value["name"], value["arguments"])
            for _, value in sorted(calls.items())
        )
        yield AssistantTurn("".join(text_parts), tool_calls, finish_reason)

    async def _stream_responses(
        self,
        *,
        model_id: str,
        messages: Sequence[dict[str, Any]],
        thinking_strength: str | None,
        tools: Sequence[dict[str, Any]] | None,
        request_params: dict[str, Any] | None,
        conversation_id: str | None,
    ) -> AsyncIterator[StreamEvent]:
        instructions, input_items = self._responses_input(messages)
        reasoning: dict[str, Any] = {"summary": "auto"}
        if thinking_strength:
            reasoning["effort"] = thinking_strength
        payload: dict[str, Any] = {
            "model": model_id,
            "instructions": instructions,
            "input": input_items,
            "tools": self._responses_tools(tools or ()),
            "tool_choice": "auto",
            "parallel_tool_calls": False,
            "reasoning": reasoning,
            "store": False,
            "stream": True,
            "include": ["reasoning.encrypted_content"],
            "prompt_cache_key": conversation_id or str(uuid4()),
        }
        payload.update(request_params or {})
        headers = {**self.headers, "Accept": "text/event-stream"}
        text_parts: list[str] = []
        calls: dict[int, dict[str, str]] = {}
        item_indexes: dict[str, int] = {}
        finish_reason = None
        async with self.client.stream(
            "POST", f"{self.base_url}/responses", headers=headers, json=payload
        ) as response:
            if response.is_error:
                await response.aread()
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data or data == "[DONE]":
                    continue
                event = json.loads(data)
                event_type = event.get("type")
                if event_type == "response.output_text.delta":
                    delta = event.get("delta")
                    if isinstance(delta, str) and delta:
                        text_parts.append(delta)
                        yield TextDelta(delta)
                elif event_type == "response.output_item.added":
                    item = event.get("item") or {}
                    if item.get("type") == "function_call":
                        index = int(event.get("output_index", len(calls)))
                        calls[index] = self._responses_call(item)
                        if item.get("id"):
                            item_indexes[item["id"]] = index
                elif event_type == "response.function_call_arguments.delta":
                    index = self._response_call_index(event, item_indexes, calls)
                    calls.setdefault(index, {"id": "", "name": "", "arguments": ""})[
                        "arguments"
                    ] += str(event.get("delta") or "")
                elif event_type == "response.output_item.done":
                    item = event.get("item") or {}
                    if item.get("type") == "function_call":
                        index = self._response_call_index(event, item_indexes, calls)
                        completed = self._responses_call(item)
                        current = calls.setdefault(index, completed)
                        current["id"] = completed["id"] or current["id"]
                        current["name"] = completed["name"] or current["name"]
                        current["arguments"] = completed["arguments"] or current["arguments"]
                elif event_type == "response.completed":
                    finish_reason = "tool_calls" if calls else "stop"
                elif event_type in {"response.failed", "error"}:
                    error = event.get("error") or (event.get("response") or {}).get("error") or {}
                    message = error.get("message") if isinstance(error, dict) else str(error)
                    code = str(error.get("code") or "") if isinstance(error, dict) else ""
                    detail = str(message or event_type)
                    raise ProviderError(
                        f"Provider response failed: {detail}",
                        retryable=self._retryable_event_error(code, detail),
                    )
        tool_calls = tuple(
            ToolCall(value["id"], value["name"], value["arguments"])
            for _, value in sorted(calls.items())
        )
        yield AssistantTurn("".join(text_parts), tool_calls, finish_reason)

    @staticmethod
    def _responses_call(item: dict[str, Any]) -> dict[str, str]:
        return {
            "id": str(item.get("call_id") or item.get("id") or ""),
            "name": str(item.get("name") or ""),
            "arguments": str(item.get("arguments") or ""),
        }

    @staticmethod
    def _response_call_index(
        event: dict[str, Any], item_indexes: dict[str, int], calls: dict[int, dict[str, str]]
    ) -> int:
        if event.get("output_index") is not None:
            return int(event["output_index"])
        item_id = event.get("item_id") or (event.get("item") or {}).get("id")
        if item_id in item_indexes:
            return item_indexes[item_id]
        return max(calls, default=-1) + 1

    @staticmethod
    def _responses_tools(tools: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        for tool in tools:
            function = tool.get("function") or {}
            if tool.get("type") != "function" or not function.get("name"):
                continue
            result.append(
                {
                    "type": "function",
                    "name": function["name"],
                    "description": function.get("description", ""),
                    "parameters": function.get("parameters", {}),
                    "strict": False,
                }
            )
        return result

    @staticmethod
    def _responses_input(
        messages: Sequence[dict[str, Any]],
    ) -> tuple[str, list[dict[str, Any]]]:
        instructions = []
        input_items = []
        for message in messages:
            role = message.get("role")
            content = message.get("content")
            if role in {"system", "developer"}:
                if content:
                    instructions.append(str(content))
                continue
            if role == "tool":
                input_items.append(
                    {
                        "type": "function_call_output",
                        "call_id": message.get("tool_call_id", ""),
                        "output": str(content or ""),
                    }
                )
                continue
            if role not in {"user", "assistant"}:
                continue
            if content:
                input_items.append(
                    {
                        "type": "message",
                        "role": role,
                        "content": [
                            {
                                "type": "input_text" if role == "user" else "output_text",
                                "text": str(content),
                            }
                        ],
                    }
                )
            if role == "assistant":
                for call in message.get("tool_calls") or []:
                    function = call.get("function") or {}
                    input_items.append(
                        {
                            "type": "function_call",
                            "call_id": call.get("id", ""),
                            "name": function.get("name", ""),
                            "arguments": function.get("arguments", ""),
                        }
                    )
        return "\n\n".join(instructions), input_items

    def _safe_error(self, prefix: str, error: Exception) -> str:
        detail = str(error)
        if isinstance(error, httpx.HTTPStatusError):
            with suppress(httpx.HTTPError, UnicodeError):
                response_detail = error.response.text.strip()
                if response_detail:
                    detail = f"{detail}: {response_detail[:1200]}"
        if self.api_key:
            detail = detail.replace(self.api_key, "[redacted]")
        return f"{prefix}: {detail}"

    def _safe_response_body(self, response: httpx.Response) -> str | None:
        with suppress(httpx.HTTPError, UnicodeError):
            body = response.text.strip()
            if self.api_key:
                body = body.replace(self.api_key, "[redacted]")
            return body[:1200] or None
        return None

    @staticmethod
    def _retryable_status(status_code: int) -> bool:
        return status_code in {408, 409, 425, 429} or status_code >= 500

    @staticmethod
    def _retryable_event_error(code: str, message: str) -> bool:
        value = f"{code} {message}".lower()
        markers = (
            "server_error",
            "rate_limit",
            "overloaded",
            "temporarily unavailable",
            "timeout",
            "connection",
        )
        return any(marker in value for marker in markers)
