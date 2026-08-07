import json

import pytest

from desktop_agent.domain.models import MessageRole, MessageStatus, SessionStatus, ToolRunStatus
from desktop_agent.storage.database import Database
from desktop_agent.storage.repositories import InvalidSessionState, Repository


@pytest.fixture
def repository(tmp_path):
    database = Database(tmp_path / "agent.sqlite3")
    repository = Repository(database)
    yield repository
    database.close()


def test_create_session_starts_active(repository, tmp_path):
    session = repository.create_session("Draft", str(tmp_path / "workspace"))

    assert session.status is SessionStatus.ACTIVE
    assert session.title == "Draft"
    assert session.workspace_path == str(tmp_path / "workspace")


def test_archive_and_restore_only_change_status(repository, tmp_path):
    session = repository.create_session("Draft", str(tmp_path))

    archived = repository.archive_session(session.id)
    assert archived.status is SessionStatus.ARCHIVED
    assert archived.title == session.title
    assert archived.workspace_path == session.workspace_path

    restored = repository.restore_session(session.id)
    assert restored.status is SessionStatus.ACTIVE
    assert restored.title == session.title


def test_delete_archived_session_cascades_related_rows(repository, tmp_path):
    session = repository.create_session("Draft", str(tmp_path))
    repository.append_message(session.id, MessageRole.USER, "hello")
    repository.append_tool_run(session.id, "shell", {"command": "Get-Date"}, "output", ToolRunStatus.COMPLETED)

    with pytest.raises(InvalidSessionState):
        repository.delete_session(session.id)

    repository.archive_session(session.id)
    repository.delete_session(session.id)

    assert repository.get_session(session.id) is None
    assert repository.list_messages(session.id) == []
    assert repository.list_tool_runs(session.id) == []


def test_assistant_message_persists_metadata_without_secrets(repository, tmp_path):
    session = repository.create_session("Draft", str(tmp_path))

    message = repository.append_message(
        session.id,
        MessageRole.ASSISTANT,
        "draft",
        model_id="gpt-5",
        thinking_strength="high",
        request_params={"temperature": 0.2, "api_key": "hidden", "nested": {"token": "nope", "top_p": 0.8}},
        status=MessageStatus.STOPPED,
        completion_marker=False,
    )

    assert message.role is MessageRole.ASSISTANT
    assert message.model_id == "gpt-5"
    assert message.thinking_strength == "high"
    assert message.request_params == {"temperature": 0.2, "nested": {"top_p": 0.8}}
    assert message.status is MessageStatus.STOPPED
    assert message.completion_marker is False


def test_tool_context_and_raw_output_are_stored_separately(repository, tmp_path):
    session = repository.create_session("Draft", str(tmp_path))

    context = {"command": "Get-Date", "metadata": {"cwd": "C:\\work"}}
    message = repository.append_message(session.id, MessageRole.TOOL, context)
    run = repository.append_tool_run(session.id, "shell", context, "raw\noutput", ToolRunStatus.FAILED)

    assert json.loads(message.content) == context
    assert json.loads(run.input_json) == context
    assert run.raw_output == "raw\noutput"
    assert run.status is ToolRunStatus.FAILED
