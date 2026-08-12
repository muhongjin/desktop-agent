import json

import httpx
import pytest
from fake_openai_server import sse_response

from desktop_agent.providers.openai_compatible import (
    AssistantTurn,
    ModelDiscoveryError,
    OpenAICompatibleClient,
    ProviderError,
    ProviderTimeout,
    TextDelta,
    ToolCall,
)


def test_owned_client_keeps_idle_connections_for_five_minutes(monkeypatch):
    captured = {}

    class Client:
        async def aclose(self):
            pass

    def build_client(**kwargs):
        captured.update(kwargs)
        return Client()

    monkeypatch.setattr("desktop_agent.providers.openai_compatible.httpx.AsyncClient", build_client)
    OpenAICompatibleClient("https://example.test/v1")

    assert captured["limits"].max_connections == 20
    assert captured["limits"].max_keepalive_connections == 10
    assert captured["limits"].keepalive_expiry == 300


@pytest.mark.asyncio
async def test_discover_models_returns_ids():
    async def handler(request):
        assert request.url.path == "/v1/models"
        return httpx.Response(200, json={"data": [{"id": "model-a"}, {"id": "model-b"}]})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = OpenAICompatibleClient("https://example.test/v1", "key", client=http)
        assert await client.discover_models() == ["model-a", "model-b"]


@pytest.mark.asyncio
async def test_discovery_failure_allows_manual_fallback():
    transport = httpx.MockTransport(lambda request: httpx.Response(503, request=request))
    async with httpx.AsyncClient(transport=transport) as http:
        client = OpenAICompatibleClient("https://example.test/v1", "key", client=http)
        with pytest.raises(ModelDiscoveryError, match="enter a model ID manually"):
            await client.discover_models()


@pytest.mark.asyncio
async def test_stream_chat_yields_text_and_final_turn():
    events = [
        {"choices": [{"delta": {"content": "hello "}, "finish_reason": None}]},
        {"choices": [{"delta": {"content": "world"}, "finish_reason": "stop"}]},
    ]
    transport = httpx.MockTransport(lambda request: sse_response(events))
    async with httpx.AsyncClient(transport=transport) as http:
        client = OpenAICompatibleClient("https://example.test/v1", client=http)
        result = [event async for event in client.stream_chat(model_id="model-a", messages=[])]
    assert result == [
        TextDelta("hello "),
        TextDelta("world"),
        AssistantTurn("hello world", (), "stop"),
    ]


@pytest.mark.asyncio
async def test_stream_chat_collects_tool_call_fragments():
    events = [
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [{"index": 0, "id": "call-1", "function": {"name": "list_"}}]
                    },
                    "finish_reason": None,
                }
            ]
        },
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {"index": 0, "function": {"name": "files", "arguments": '{"path":'}}
                        ]
                    },
                    "finish_reason": None,
                }
            ]
        },
        {
            "choices": [
                {
                    "delta": {"tool_calls": [{"index": 0, "function": {"arguments": '"."}'}}]},
                    "finish_reason": "tool_calls",
                }
            ]
        },
    ]
    transport = httpx.MockTransport(lambda request: sse_response(events))
    async with httpx.AsyncClient(transport=transport) as http:
        client = OpenAICompatibleClient("https://example.test/v1", client=http)
        result = [event async for event in client.stream_chat(model_id="model-a", messages=[])]
    turn = result[-1]
    assert turn.tool_calls[0].id == "call-1"
    assert turn.tool_calls[0].name == "list_files"
    assert turn.tool_calls[0].arguments == '{"path":"."}'


@pytest.mark.asyncio
async def test_responses_protocol_builds_codex_payload_and_streams_text():
    captured = {}
    events = [
        {"type": "response.created"},
        {"type": "response.output_text.delta", "delta": "O"},
        {"type": "response.output_text.delta", "delta": "K"},
        {"type": "response.completed"},
    ]

    async def handler(request):
        captured["path"] = request.url.path
        captured["accept"] = request.headers.get("accept")
        captured["payload"] = json.loads(request.content)
        return sse_response(events)

    messages = [
        {"role": "system", "content": "System instructions"},
        {"role": "user", "content": "Reply OK"},
    ]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a file",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = OpenAICompatibleClient(
            "https://example.test/v1", client=http, api_protocol="responses"
        )
        result = [
            event
            async for event in client.stream_chat(
                model_id="model-a",
                messages=messages,
                thinking_strength="medium",
                tools=tools,
                conversation_id="session-1",
            )
        ]

    payload = captured["payload"]
    assert captured["path"] == "/v1/responses"
    assert captured["accept"] == "text/event-stream"
    assert payload["instructions"] == "System instructions"
    assert payload["input"][0]["content"][0] == {"type": "input_text", "text": "Reply OK"}
    assert payload["tools"][0]["name"] == "read_file"
    assert payload["reasoning"] == {"summary": "auto", "effort": "medium"}
    assert payload["tool_choice"] == "auto"
    assert payload["store"] is False
    assert payload["stream"] is True
    assert payload["prompt_cache_key"] == "session-1"
    assert result == [TextDelta("O"), TextDelta("K"), AssistantTurn("OK", (), "stop")]


@pytest.mark.asyncio
async def test_responses_protocol_converts_function_calls_and_tool_history():
    captured = {}
    events = [
        {
            "type": "response.output_item.added",
            "output_index": 0,
            "item": {
                "type": "function_call",
                "id": "fc-1",
                "call_id": "call-2",
                "name": "read_file",
                "arguments": "",
            },
        },
        {
            "type": "response.function_call_arguments.delta",
            "output_index": 0,
            "delta": '{"path":"notes.txt"}',
        },
        {
            "type": "response.output_item.done",
            "output_index": 0,
            "item": {
                "type": "function_call",
                "id": "fc-1",
                "call_id": "call-2",
                "name": "read_file",
                "arguments": '{"path":"notes.txt"}',
            },
        },
        {"type": "response.completed"},
    ]

    async def handler(request):
        captured["payload"] = json.loads(request.content)
        return sse_response(events)

    history = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {"name": "list_files", "arguments": '{"path":"."}'},
                }
            ],
        },
        {"role": "tool", "content": "notes.txt", "tool_call_id": "call-1"},
    ]
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = OpenAICompatibleClient(
            "https://example.test/v1", client=http, api_protocol="responses"
        )
        result = [event async for event in client.stream_chat(model_id="model-a", messages=history)]

    assert captured["payload"]["input"] == [
        {
            "type": "function_call",
            "call_id": "call-1",
            "name": "list_files",
            "arguments": '{"path":"."}',
        },
        {"type": "function_call_output", "call_id": "call-1", "output": "notes.txt"},
    ]
    assert result[-1] == AssistantTurn(
        "", (ToolCall("call-2", "read_file", '{"path":"notes.txt"}'),), "tool_calls"
    )


@pytest.mark.asyncio
async def test_provider_error_redacts_key():
    secret = "super-secret-key"

    def handler(request):
        return httpx.Response(401, text=secret, request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = OpenAICompatibleClient("https://example.test/v1", secret, client=http)
        with pytest.raises(ProviderError) as captured:
            async for _ in client.stream_chat(model_id="model-a", messages=[]):
                pass
    assert secret not in str(captured.value)
    assert secret not in (captured.value.response_body or "")


@pytest.mark.asyncio
async def test_stream_error_includes_provider_response_detail():
    def handler(request):
        return httpx.Response(
            400,
            json={"error": {"message": "prompt is too long: 1100000 tokens > 1000000 maximum"}},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = OpenAICompatibleClient(
            "https://example.test/v1", client=http, api_protocol="responses"
        )
        with pytest.raises(ProviderError, match="prompt is too long"):
            async for _ in client.stream_chat(model_id="model-a", messages=[]):
                pass


@pytest.mark.asyncio
@pytest.mark.parametrize(("status", "retryable"), [(401, False), (429, True), (502, True)])
async def test_http_status_sets_retryable_classification(status, retryable):
    def handler(request):
        return httpx.Response(status, json={"error": {"message": "failed"}}, request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = OpenAICompatibleClient("https://example.test/v1", client=http)
        with pytest.raises(ProviderError) as captured:
            async for _ in client.stream_chat(model_id="model-a", messages=[]):
                pass
    assert captured.value.retryable is retryable
    assert captured.value.status_code == status
    assert "failed" in (captured.value.response_body or "")


@pytest.mark.asyncio
async def test_stream_timeout_is_normalized_without_retry():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("slow provider", request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = OpenAICompatibleClient("https://example.test/v1", client=http)
        with pytest.raises(ProviderTimeout, match="timed out") as captured:
            async for _ in client.stream_chat(model_id="model-a", messages=[]):
                pass
    assert calls == 1
    assert captured.value.retryable is True
