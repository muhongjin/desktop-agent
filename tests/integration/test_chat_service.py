import asyncio
import time
from datetime import UTC, datetime

import pytest
from PySide6.QtCore import QObject, Signal

from desktop_agent.chat_service import ChatService
from desktop_agent.domain.models import MessageRole, ProviderConfig
from desktop_agent.providers.openai_compatible import AssistantTurn, TextDelta
from desktop_agent.security.permissions import PermissionBroker
from desktop_agent.storage.database import Database
from desktop_agent.storage.repositories import Repository


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
