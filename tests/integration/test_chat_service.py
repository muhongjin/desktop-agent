import asyncio
import time
from datetime import UTC, datetime

import pytest
from PySide6.QtCore import QObject, Signal

from desktop_agent.chat_service import ChatService, MessageListModel
from desktop_agent.domain.models import MessageRole, MessageStatus, ProviderConfig, ToolRunStatus
from desktop_agent.providers.openai_compatible import AssistantTurn, TextDelta
from desktop_agent.security.permissions import PermissionBroker, PermissionRequest
from desktop_agent.storage.database import Database
from desktop_agent.storage.repositories import Repository
from desktop_agent.tools.registry import RegisteredTool


class Sessions(QObject):
    currentSessionChanged = Signal()

    def __init__(self, session_id):
        super().__init__()
        self.currentSessionId = session_id
        self.fullAccess = False


class Settings:
    systemPrompt = "Be concise"
    shellMode = "auto"


class Credentials:
    def get(self, provider_id):
        return "secret"


class SlowCredentials:
    def get(self, provider_id):
        time.sleep(0.15)
        return "secret"


class Provider:
    def __init__(self):
        self.requests = []
        self.closed = False

    async def stream_chat(self, **request):
        self.requests.append(request)
        yield TextDelta("hello")
        yield AssistantTurn("hello", (), "stop")

    async def close(self):
        self.closed = True


class DelayedTitleProvider(Provider):
    def __init__(self):
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def stream_chat(self, **request):
        self.requests.append(request)
        self.started.set()
        await self.release.wait()
        title = "**标题：桌面 Agent 设计**\n这是一段多余解释"
        yield TextDelta(title)
        yield AssistantTurn(title, (), "stop")


class FailingTitleProvider(Provider):
    async def stream_chat(self, **request):
        self.requests.append(request)
        raise RuntimeError("title request failed")
        yield


@pytest.mark.asyncio
async def test_chat_service_runs_real_loop_and_safe_mode_hides_tools(tmp_path):
    database = Database(tmp_path / "agent.sqlite3")
    repo = Repository(database)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    session = repo.create_session("Draft", str(workspace), current_model_id="openai:model-a")
    now = datetime.now(UTC)
    repo.set_provider_config(
        ProviderConfig(
            "openai", "OpenAI", "https://example.test/v1", {"models": ["model-a"]}, now, now
        )
    )
    provider = Provider()
    service = ChatService(
        repo,
        Sessions(session.id),
        None,
        Settings(),
        PermissionBroker(),
        Credentials(),
        safe_mode=True,
        provider_factory=lambda base_url, api_key: provider,
    )
    service.sendMessage("hi")
    while service.running:
        await asyncio.sleep(0.01)
    messages = repo.list_messages(session.id)
    assert [message.role for message in messages] == [MessageRole.USER, MessageRole.ASSISTANT]
    assert messages[-1].content == "hello"
    assert provider.requests[0]["tools"] == ()
    assert provider.closed is True
    database.close()


@pytest.mark.asyncio
async def test_send_returns_immediately_and_streaming_does_not_reload_per_delta(tmp_path):
    database = Database(tmp_path / "agent.sqlite3")
    repo = Repository(database)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    session = repo.create_session("Draft", str(workspace), current_model_id="openai:model-a")
    now = datetime.now(UTC)
    repo.set_provider_config(
        ProviderConfig(
            "openai", "OpenAI", "https://example.test/v1", {"models": ["model-a"]}, now, now
        )
    )

    class BurstProvider(Provider):
        async def stream_chat(self, **request):
            self.requests.append(request)
            for _ in range(100):
                yield TextDelta("x")
            yield AssistantTurn("x" * 100, (), "stop")

    provider = BurstProvider()
    service = ChatService(
        repo,
        Sessions(session.id),
        None,
        Settings(),
        PermissionBroker(),
        SlowCredentials(),
        safe_mode=True,
        provider_factory=lambda base_url, api_key: provider,
    )
    original_list = repo.list_messages
    list_count = 0

    def counted_list(*args, **kwargs):
        nonlocal list_count
        list_count += 1
        return original_list(*args, **kwargs)

    repo.list_messages = counted_list
    started = time.perf_counter()
    service.sendMessage("hi")
    elapsed = time.perf_counter() - started
    while service.running:
        await asyncio.sleep(0.01)

    assert elapsed < 0.05
    assert list_count <= 2
    assert original_list(session.id)[-1].content == "x" * 100
    database.close()


@pytest.mark.asyncio
async def test_first_message_generates_title_without_blocking_main_response(tmp_path):
    database = Database(tmp_path / "agent.sqlite3")
    repo = Repository(database)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    session = repo.create_session(
        "新对话", str(workspace), current_model_id="openai:model-a"
    )
    now = datetime.now(UTC)
    repo.set_provider_config(
        ProviderConfig(
            "openai", "OpenAI", "https://example.test/v1", {"models": ["model-a"]}, now, now
        )
    )
    main_provider = Provider()
    title_provider = DelayedTitleProvider()
    service = ChatService(
        repo,
        Sessions(session.id),
        None,
        Settings(),
        PermissionBroker(),
        Credentials(),
        safe_mode=True,
        provider_factory=lambda base_url, api_key: main_provider,
        title_provider_factory=lambda base_url, api_key: title_provider,
    )
    changed = []
    service.sessionTitleChanged.connect(changed.append)

    service.sendMessage("设计一个简单的桌面 Agent")
    await title_provider.started.wait()
    while service.running:
        await asyncio.sleep(0.01)

    assert repo.get_session(session.id).title == "新对话"
    assert service._title_tasks
    title_provider.release.set()
    while service._title_tasks:
        await asyncio.sleep(0.01)

    assert repo.get_session(session.id).title == "桌面 Agent 设计"
    assert changed == [session.id]
    assert title_provider.requests[0]["tools"] == ()

    service.sendMessage("继续")
    while service.running:
        await asyncio.sleep(0.01)
    assert len(title_provider.requests) == 1
    database.close()


@pytest.mark.asyncio
async def test_title_failure_uses_first_message_without_affecting_reply(tmp_path):
    database = Database(tmp_path / "agent.sqlite3")
    repo = Repository(database)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    session = repo.create_session(
        "新对话", str(workspace), current_model_id="openai:model-a"
    )
    now = datetime.now(UTC)
    repo.set_provider_config(
        ProviderConfig(
            "openai", "OpenAI", "https://example.test/v1", {"models": ["model-a"]}, now, now
        )
    )
    main_provider = Provider()
    title_provider = FailingTitleProvider()
    service = ChatService(
        repo,
        Sessions(session.id),
        None,
        Settings(),
        PermissionBroker(),
        Credentials(),
        safe_mode=True,
        provider_factory=lambda base_url, api_key: main_provider,
        title_provider_factory=lambda base_url, api_key: title_provider,
    )

    service.sendMessage("排查发送消息时的界面卡顿问题")
    while service.running or service._title_tasks:
        await asyncio.sleep(0.01)

    assert repo.get_session(session.id).title == "排查发送消息时的界面卡顿问题"
    assert repo.list_messages(session.id)[-1].content == "hello"
    assert title_provider.closed is True
    database.close()


def test_message_model_exposes_structured_tool_run_fields(tmp_path):
    database = Database(tmp_path / "agent.sqlite3")
    repo = Repository(database)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    session = repo.create_session("Draft", str(workspace))
    repo.append_tool_run(
        session.id,
        "run_powershell",
        {"command": "Get-ChildItem"},
        "access denied",
        ToolRunStatus.FAILED,
    )
    repo.append_message(session.id, MessageRole.TOOL, "命令执行失败")

    model = MessageListModel(repo)
    model.load(session.id)
    index = model.index(0, 0)

    assert model.data(index, model.ToolNameRole) == "run_powershell"
    assert model.data(index, model.ToolStatusRole) == "failed"
    assert "Get-ChildItem" in model.data(index, model.ToolInputRole)
    assert model.data(index, model.DetailsRole) == "access denied"
    database.close()


def test_stopped_message_does_not_add_status_text(tmp_path):
    database = Database(tmp_path / "agent.sqlite3")
    repo = Repository(database)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    session = repo.create_session("Draft", str(workspace))
    repo.append_message(
        session.id,
        MessageRole.ASSISTANT,
        "已生成的内容",
        status=MessageStatus.STOPPED,
        completion_marker=True,
    )

    model = MessageListModel(repo)
    model.load(session.id)

    assert model.data(model.index(0, 0), model.ContentRole) == "已生成的内容"
    database.close()


@pytest.mark.asyncio
async def test_session_permission_is_reused_and_can_be_cleared(tmp_path):
    database = Database(tmp_path / "agent.sqlite3")
    repo = Repository(database)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    session = repo.create_session("Draft", str(workspace))
    sessions = Sessions(session.id)
    service = ChatService(
        repo,
        sessions,
        None,
        Settings(),
        PermissionBroker(),
        Credentials(),
        safe_mode=True,
    )
    service._active_session_id = session.id
    requests = []
    service.permissionRequested.connect(lambda *values: requests.append(values))
    tool = RegisteredTool(
        "delete_path",
        "Delete a path",
        {},
        lambda path: None,
        "fs.delete",
    )
    request = PermissionRequest("fs.delete", workspace / "result.txt")

    first = asyncio.create_task(service._confirm_permission(request, tool, {"path": "result.txt"}))
    await asyncio.sleep(0)
    service.resolvePermission("session")
    assert await first is True
    assert await service._confirm_permission(request, tool, {"path": "other.txt"}) is True
    assert len(requests) == 1

    service.clearSessionPermissions(session.id)
    third = asyncio.create_task(service._confirm_permission(request, tool, {"path": "third.txt"}))
    await asyncio.sleep(0)
    service.resolvePermission("deny")
    assert await third is False
    assert len(requests) == 2
    database.close()
