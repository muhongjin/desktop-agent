import asyncio
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
    repo.set_provider_config(ProviderConfig("openai", "OpenAI", "https://example.test/v1", {"models": ["model-a"]}, now, now))
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
