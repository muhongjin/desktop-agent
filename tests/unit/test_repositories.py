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


def test_generated_session_title_is_unique_across_active_and_archived_chats(
    repository, tmp_path
):
    repository.create_session("项目规划", str(tmp_path / "active"))
    archived = repository.create_session("项目规划（2）", str(tmp_path / "archived"))
    repository.archive_session(archived.id)
    target = repository.create_session("新对话", str(tmp_path / "target"))

    updated = repository.set_unique_session_title(target.id, "项目规划")

    assert updated.title == "项目规划（3）"


def test_generated_session_title_respects_length_limit(repository, tmp_path):
    title = "这是一个非常长而且需要被截断的会话标题用于测试"
    repository.create_session(title[:24], str(tmp_path / "existing"))
    target = repository.create_session("新对话", str(tmp_path / "target"))

    updated = repository.set_unique_session_title(target.id, title)

    assert len(updated.title) <= 24
    assert updated.title.endswith("（2）")


def test_delete_archived_session_cascades_related_rows(repository, tmp_path):
    session = repository.create_session("Draft", str(tmp_path))
    repository.append_message(session.id, MessageRole.USER, "hello")
    repository.append_tool_run(
        session.id, "shell", {"command": "Get-Date"}, "output", ToolRunStatus.COMPLETED
    )

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
        request_params={
            "temperature": 0.2,
            "api_key": "hidden",
            "nested": {"token": "nope", "top_p": 0.8},
        },
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
    run = repository.append_tool_run(
        session.id, "shell", context, "raw\noutput", ToolRunStatus.FAILED
    )

    assert json.loads(message.content) == context
    assert json.loads(run.input_json) == context
    assert run.raw_output == "raw\noutput"
    assert run.status is ToolRunStatus.FAILED


def test_session_preference_changes_do_not_rewrite_message_snapshot(repository, tmp_path):
    session = repository.create_session(
        "Draft", str(tmp_path), current_model_id="openai:model-a", thinking_strength="medium"
    )
    message = repository.append_message(
        session.id,
        MessageRole.ASSISTANT,
        "answer",
        model_id="model-a",
        thinking_strength="medium",
    )
    updated = repository.update_session_preferences(
        session.id, model_id="openai:model-b", thinking_strength="high"
    )
    persisted = repository.list_messages(session.id)[0]
    assert updated.current_model_id == "openai:model-b"
    assert updated.thinking_strength == "high"
    assert persisted.model_id == message.model_id == "model-a"
    assert persisted.thinking_strength == message.thinking_strength == "medium"


def test_database_records_schema_version(repository):
    row = repository.database.execute(
        "SELECT value FROM schema_meta WHERE key = 'schema_version'"
    ).fetchone()
    assert row["value"] == "3"
