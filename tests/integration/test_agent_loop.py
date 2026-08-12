import asyncio

import pytest

from desktop_agent.agent.loop import AgentLoop
from desktop_agent.agent.prompt import PromptComposer
from desktop_agent.agent.session_retry import SessionRetry
from desktop_agent.domain.models import MessageRole, MessageStatus, ToolRunStatus
from desktop_agent.providers.openai_compatible import (
    AssistantTurn,
    ProviderError,
    TextDelta,
    ToolCall,
)
from desktop_agent.security.permissions import PermissionBroker, SessionAccess
from desktop_agent.storage.database import Database
from desktop_agent.storage.repositories import Repository
from desktop_agent.tools.files import FileTools
from desktop_agent.tools.registry import RegisteredTool, file_tool_registry


class SequenceProvider:
    def __init__(self, turns):
        self.turns = list(turns)
        self.requests = []

    async def stream_chat(self, **request):
        self.requests.append(request)
        turn = self.turns.pop(0)
        if isinstance(turn, Exception):
            raise turn
        for event in turn:
            yield event


class RecordingPromptComposer(PromptComposer):
    def __init__(self):
        super().__init__()
        self.truncate_values = []

    def compose(self, *args, **kwargs):
        self.truncate_values.append(kwargs.get("truncate", False))
        return super().compose(*args, **kwargs)


@pytest.fixture
def loop_context(tmp_path):
    database = Database(tmp_path / "agent.sqlite3")
    repo = Repository(database)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    session = repo.create_session("Draft", str(workspace))
    access = SessionAccess.local(workspace)
    broker = PermissionBroker()
    registry = file_tool_registry(FileTools(broker, access))
    yield database, repo, session, access, broker, registry
    database.close()


@pytest.mark.asyncio
async def test_loop_streams_text_and_preserves_model_snapshot(loop_context):
    _, repo, session, access, broker, registry = loop_context
    provider = SequenceProvider([[TextDelta("hello"), AssistantTurn("hello", (), "stop")]])
    loop = AgentLoop(repo, PromptComposer(), provider, broker, registry)
    events = [
        event
        async for event in loop.send_message(
            session.id, "hi", model_id="deepseek-chat", thinking_strength="medium", access=access
        )
    ]
    messages = repo.list_messages(session.id)
    assistant = messages[-1]
    assert [event.type for event in events] == [
        "turn_started",
        "text_delta",
        "turn_finished",
    ]
    assert assistant.content == "hello"
    assert assistant.status is MessageStatus.COMPLETE
    assert assistant.model_id == "deepseek-chat"
    assert assistant.thinking_strength == "medium"


@pytest.mark.asyncio
async def test_tool_call_passes_permission_and_persists_context(loop_context):
    _, repo, session, access, broker, registry = loop_context
    call = ToolCall("call-1", "write_file", '{"path":"answer.txt","content":"42"}')
    provider = SequenceProvider(
        [
            [AssistantTurn("", (call,), "tool_calls")],
            [TextDelta("done"), AssistantTurn("done", (), "stop")],
        ]
    )
    composer = RecordingPromptComposer()
    loop = AgentLoop(
        repo,
        composer,
        provider,
        broker,
        registry,
        context_limit=128_000,
    )
    events = [
        event
        async for event in loop.send_message(
            session.id, "write", model_id="model-a", thinking_strength=None, access=access
        )
    ]
    assert (access.workspace / "answer.txt").read_text() == "42"
    assert [event.type for event in events] == [
        "turn_started",
        "tool_started",
        "tool_finished",
        "turn_started",
        "text_delta",
        "turn_finished",
    ]
    tool_message = next(
        message for message in repo.list_messages(session.id) if message.role is MessageRole.TOOL
    )
    assert tool_message.tool_call_id == "call-1"
    assert repo.list_tool_runs(session.id)[0].status is ToolRunStatus.COMPLETED
    assert composer.truncate_values == [True, False]
    followup = provider.requests[1]["messages"]
    assistant_call = next(message for message in followup if message.get("tool_calls"))
    tool_result = next(message for message in followup if message["role"] == "tool")
    assert assistant_call["tool_calls"][0]["id"] == "call-1"
    assert tool_result["tool_call_id"] == "call-1"


@pytest.mark.asyncio
async def test_stop_keeps_partial_text_and_prevents_more_work(loop_context):
    _, repo, session, access, broker, registry = loop_context

    class SlowProvider:
        async def stream_chat(self, **request):
            yield TextDelta("partial")
            await asyncio.sleep(30)
            yield AssistantTurn("partial late", (), "stop")

    stop = asyncio.Event()
    loop = AgentLoop(repo, PromptComposer(), SlowProvider(), broker, registry)

    async def collect():
        return [
            event
            async for event in loop.send_message(
                session.id,
                "hi",
                model_id="model-a",
                thinking_strength=None,
                access=access,
                stop_event=stop,
            )
        ]

    task = asyncio.create_task(collect())
    await asyncio.sleep(0.05)
    stop.set()
    events = await asyncio.wait_for(task, timeout=2)
    assistant = repo.list_messages(session.id)[-1]
    assert assistant.content == "partial"
    assert assistant.status is MessageStatus.STOPPED
    assert assistant.completion_marker is True
    assert events[-1].type == "turn_stopped"


@pytest.mark.asyncio
async def test_provider_error_is_visible_and_not_retried(loop_context):
    _, repo, session, access, broker, registry = loop_context
    provider = SequenceProvider([ProviderError("provider failed")])
    loop = AgentLoop(repo, PromptComposer(), provider, broker, registry)
    events = [
        event
        async for event in loop.send_message(
            session.id, "hi", model_id="model-a", thinking_strength=None, access=access
        )
    ]
    assert len(provider.requests) == 1
    assert events[-1].type == "turn_stopped"
    assert "provider failed" in events[-1].data["error"]
    assert "provider failed" in repo.list_messages(session.id)[-1].content


@pytest.mark.asyncio
async def test_context_error_is_not_retried(loop_context):
    _, repo, session, access, broker, registry = loop_context
    for index in range(3):
        repo.append_message(session.id, MessageRole.USER, f"old question {index}")
        repo.append_message(session.id, MessageRole.ASSISTANT, f"old answer {index}")
    provider = SequenceProvider([ProviderError("maximum context length exceeded")])
    loop = AgentLoop(
        repo,
        PromptComposer(),
        provider,
        broker,
        registry,
        context_limit=None,
    )
    events = [
        event
        async for event in loop.send_message(
            session.id, "new question", model_id="model-a", thinking_strength=None, access=access
        )
    ]
    assert len(provider.requests) == 1
    assert events[-1].type == "turn_stopped"
    assert events[-1].data["context_overflow"] is True
    assert "maximum context length exceeded" in repo.list_messages(session.id)[-1].content


@pytest.mark.asyncio
async def test_non_retryable_provider_error_is_not_retried(loop_context):
    _, repo, session, access, broker, registry = loop_context
    provider = SequenceProvider([ProviderError("401 Unauthorized", status_code=401)])
    loop = AgentLoop(
        repo,
        PromptComposer(),
        provider,
        broker,
        registry,
        context_limit=100,
    )
    events = [
        event
        async for event in loop.send_message(
            session.id, "hi", model_id="model-a", thinking_strength=None, access=access
        )
    ]
    assert len(provider.requests) == 1
    assert events[-1].type == "turn_stopped"


@pytest.mark.asyncio
async def test_retryable_provider_error_succeeds_on_fifth_attempt(loop_context):
    _, repo, session, access, broker, registry = loop_context
    provider = SequenceProvider(
        [
            ProviderError("temporary connection failure", retryable=True),
            ProviderError("temporary connection failure", retryable=True),
            ProviderError("temporary connection failure", retryable=True),
            ProviderError("temporary connection failure", retryable=True),
            [TextDelta("recovered"), AssistantTurn("recovered", (), "stop")],
        ]
    )
    loop = AgentLoop(
        repo,
        PromptComposer(),
        provider,
        broker,
        registry,
        session_retry=SessionRetry(delays=(0, 0, 0, 0)),
    )
    events = [
        event
        async for event in loop.send_message(
            session.id, "hi", model_id="model-a", thinking_strength=None, access=access
        )
    ]
    retry_events = [event for event in events if event.type == "retrying"]
    assert len(provider.requests) == 5
    assert [event.data["attempt"] for event in retry_events] == [2, 3, 4, 5]
    assert [event.data["retry_count"] for event in retry_events] == [1, 2, 3, 4]
    assert events[-1].type == "turn_finished"
    assert repo.list_messages(session.id)[-1].content == "recovered"


@pytest.mark.asyncio
async def test_retryable_provider_error_stops_after_five_attempts(loop_context):
    _, repo, session, access, broker, registry = loop_context
    provider = SequenceProvider(
        [ProviderError("temporary connection failure", retryable=True) for _ in range(5)]
    )
    loop = AgentLoop(
        repo,
        PromptComposer(),
        provider,
        broker,
        registry,
        session_retry=SessionRetry(delays=(0, 0, 0, 0)),
    )
    events = [
        event
        async for event in loop.send_message(
            session.id, "hi", model_id="model-a", thinking_strength=None, access=access
        )
    ]
    assert len(provider.requests) == 5
    assert len([event for event in events if event.type == "retrying"]) == 4
    assert events[-1].type == "turn_stopped"
    assert "temporary connection failure" in repo.list_messages(session.id)[-1].content


@pytest.mark.asyncio
async def test_retry_success_replaces_failed_attempt_partial(loop_context):
    _, repo, session, access, broker, registry = loop_context

    class PartialRetryProvider:
        def __init__(self):
            self.requests = []

        async def stream_chat(self, **request):
            self.requests.append(request)
            if len(self.requests) == 1:
                yield TextDelta("failed partial")
                raise ProviderError("connection reset", retryable=True)
            yield TextDelta("recovered")
            yield AssistantTurn("recovered", (), "stop")

    provider = PartialRetryProvider()
    loop = AgentLoop(
        repo,
        PromptComposer(),
        provider,
        broker,
        registry,
        session_retry=SessionRetry(delays=(0, 0, 0, 0)),
    )
    events = [
        event
        async for event in loop.send_message(
            session.id, "hi", model_id="model-a", thinking_strength=None, access=access
        )
    ]
    contents = [event.data["content"] for event in events if event.type == "text_delta"]
    assert contents == ["failed partial", "recovered"]
    assert repo.list_messages(session.id)[-1].content == "recovered"


@pytest.mark.asyncio
async def test_retry_exhaustion_preserves_longest_partial(loop_context):
    _, repo, session, access, broker, registry = loop_context

    class PartialFailureProvider:
        def __init__(self):
            self.requests = []

        async def stream_chat(self, **request):
            self.requests.append(request)
            partial = "longest partial" if len(self.requests) == 1 else "short"
            yield TextDelta(partial)
            raise ProviderError("connection reset", retryable=True)

    provider = PartialFailureProvider()
    loop = AgentLoop(
        repo,
        PromptComposer(),
        provider,
        broker,
        registry,
        session_retry=SessionRetry(delays=(0, 0, 0, 0)),
    )
    events = [
        event
        async for event in loop.send_message(
            session.id, "hi", model_id="model-a", thinking_strength=None, access=access
        )
    ]
    assert len(provider.requests) == 5
    assert events[-1].type == "turn_stopped"
    assert "longest partial" in repo.list_messages(session.id)[-1].content


@pytest.mark.asyncio
async def test_stop_interrupts_retry_backoff(loop_context):
    _, repo, session, access, broker, registry = loop_context
    provider = SequenceProvider([ProviderError("connection reset", retryable=True)])
    stop = asyncio.Event()
    loop = AgentLoop(
        repo,
        PromptComposer(),
        provider,
        broker,
        registry,
        session_retry=SessionRetry(delays=(30, 30, 30, 30)),
    )

    async def collect():
        return [
            event
            async for event in loop.send_message(
                session.id,
                "hi",
                model_id="model-a",
                thinking_strength=None,
                access=access,
                stop_event=stop,
            )
        ]

    task = asyncio.create_task(collect())
    await asyncio.sleep(0.05)
    stop.set()
    events = await asyncio.wait_for(task, timeout=2)
    assert len(provider.requests) == 1
    assert events[-1].type == "turn_stopped"


@pytest.mark.asyncio
async def test_stop_cancels_async_tool_without_stop_parameter(loop_context):
    _, repo, session, access, broker, _ = loop_context
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def slow_tool(path: str):
        started.set()
        try:
            await asyncio.sleep(30)
        finally:
            cancelled.set()

    registry = {
        "slow_tool": RegisteredTool(
            "slow_tool",
            "Wait",
            {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
            slow_tool,
            "fs.read",
        )
    }
    call = ToolCall("call-1", "slow_tool", '{"path":"."}')
    provider = SequenceProvider([[AssistantTurn("", (call,), "tool_calls")]])
    stop = asyncio.Event()
    loop = AgentLoop(repo, PromptComposer(), provider, broker, registry)

    async def collect():
        return [
            event
            async for event in loop.send_message(
                session.id,
                "wait",
                model_id="model-a",
                thinking_strength=None,
                access=access,
                stop_event=stop,
            )
        ]

    task = asyncio.create_task(collect())
    await asyncio.wait_for(started.wait(), timeout=2)
    stop.set()
    events = await asyncio.wait_for(task, timeout=2)
    assert cancelled.is_set()
    assert events[-1].type == "turn_stopped"


@pytest.mark.asyncio
async def test_none_mode_exposes_only_read_tools(loop_context):
    _, repo, session, access, broker, registry = loop_context
    provider = SequenceProvider([[AssistantTurn("done", (), "stop")]])
    loop = AgentLoop(repo, PromptComposer(), provider, broker, registry)
    none_access = SessionAccess.none(access.workspace)
    _ = [
        event
        async for event in loop.send_message(
            session.id, "hi", model_id="model-a", thinking_strength=None, access=none_access
        )
    ]
    names = {tool["function"]["name"] for tool in provider.requests[0]["tools"]}
    assert names == {"list_files", "read_file"}


@pytest.mark.asyncio
async def test_streaming_batches_partial_message_writes(loop_context):
    _, repo, session, access, broker, registry = loop_context
    deltas = [TextDelta("x") for _ in range(100)]
    provider = SequenceProvider([[*deltas, AssistantTurn("x" * 100, (), "stop")]])
    original_update = repo.update_message
    update_count = 0

    def counted_update(*args, **kwargs):
        nonlocal update_count
        update_count += 1
        return original_update(*args, **kwargs)

    repo.update_message = counted_update
    loop = AgentLoop(repo, PromptComposer(), provider, broker, registry)
    _ = [
        event
        async for event in loop.send_message(
            session.id, "hi", model_id="model-a", thinking_strength=None, access=access
        )
    ]

    assert update_count <= 10
    assert repo.list_messages(session.id)[-1].content == "x" * 100
