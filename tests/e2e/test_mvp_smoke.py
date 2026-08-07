import asyncio
from datetime import UTC, datetime

import pytest
from PySide6.QtCore import QObject, Signal

from desktop_agent.chat_service import ChatService
from desktop_agent.domain.models import ProviderConfig, SessionStatus, ToolRunStatus
from desktop_agent.providers.openai_compatible import AssistantTurn, TextDelta, ToolCall
from desktop_agent.security.permissions import PermissionBroker
from desktop_agent.storage.database import Database
from desktop_agent.storage.repositories import Repository
from desktop_agent.tools.powershell import ShellUnavailable, select_shell
from desktop_agent.workspaces.service import WorkspaceService


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
        return "fake-key"


class Provider:
    def __init__(self):
        self.turn = 0

    async def stream_chat(self, **request):
        self.turn += 1
        if self.turn == 1:
            yield AssistantTurn(
                "",
                (ToolCall("file-1", "write_file", '{"path":"result.txt","content":"created"}'),),
                "tool_calls",
            )
        elif self.turn == 2:
            yield AssistantTurn(
                "",
                (ToolCall("shell-1", "run_powershell", '{"command":"Write-Output smoke"}'),),
                "tool_calls",
            )
        else:
            yield TextDelta("完成")
            yield AssistantTurn("完成", (), "stop")

    async def close(self):
        return None


@pytest.mark.asyncio
async def test_mvp_file_shell_archive_restore_and_reopen(tmp_path):
    try:
        select_shell("auto")
    except ShellUnavailable:
        pytest.skip("PowerShell is not installed")
    database_path = tmp_path / "agent.sqlite3"
    database = Database(database_path)
    repo = Repository(database)
    workspaces = WorkspaceService(tmp_path / "workspaces", repo)
    session_id = "session-1"
    workspace = workspaces.create_for_session(session_id)
    now = datetime.now(UTC)
    repo.set_provider_config(
        ProviderConfig(
            "openai", "OpenAI", "https://example.test/v1", {"models": ["model-a"]}, now, now
        )
    )
    session = repo.create_session(
        "Draft",
        str(workspace),
        current_model_id="openai:model-a",
        thinking_strength="medium",
        session_id=session_id,
    )
    provider = Provider()
    chat = ChatService(
        repo,
        Sessions(session.id),
        None,
        Settings(),
        PermissionBroker(),
        Credentials(),
        provider_factory=lambda base_url, api_key: provider,
    )
    chat.sendMessage("创建文件并检查 PowerShell")
    while chat.running:
        await asyncio.sleep(0.01)
    assert (workspace / "result.txt").read_text() == "created"
    runs = repo.list_tool_runs(session.id)
    assert [run.status for run in runs] == [ToolRunStatus.COMPLETED, ToolRunStatus.COMPLETED]
    assert "smoke" in runs[1].raw_output
    repo.archive_session(session.id)
    assert repo.get_session(session.id).status is SessionStatus.ARCHIVED
    repo.restore_session(session.id)
    assert repo.get_session(session.id).status is SessionStatus.ACTIVE
    expected_messages = [message.content for message in repo.list_messages(session.id)]
    database.close()

    reopened = Database(database_path)
    reopened_repo = Repository(reopened)
    assert [
        message.content for message in reopened_repo.list_messages(session.id)
    ] == expected_messages
    assert reopened_repo.get_session(session.id).status is SessionStatus.ACTIVE
    reopened.close()
