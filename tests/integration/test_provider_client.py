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
)


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
    assert result == [TextDelta("hello "), TextDelta("world"), AssistantTurn("hello world", (), "stop")]


@pytest.mark.asyncio
async def test_stream_chat_collects_tool_call_fragments():
    events = [
        {
            "choices": [
                {
                    "delta": {"tool_calls": [{"index": 0, "id": "call-1", "function": {"name": "list_"}}]},
                    "finish_reason": None,
                }
            ]
        },
        {
            "choices": [
                {
                    "delta": {"tool_calls": [{"index": 0, "function": {"name": "files", "arguments": '{"path":'}}]},
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
        with pytest.raises(ProviderTimeout, match="timed out"):
            async for _ in client.stream_chat(model_id="model-a", messages=[]):
                pass
    assert calls == 1
