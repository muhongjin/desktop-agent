from desktop_agent.agent.prompt import PromptComposer
from desktop_agent.domain.models import MessageRole, MessageStatus
from desktop_agent.storage.database import Database
from desktop_agent.storage.repositories import Repository


def test_prompt_order_and_workspace_metadata(tmp_path):
    database = Database(tmp_path / "agent.sqlite3")
    repo = Repository(database)
    session = repo.create_session("Draft", str(tmp_path / "workspace"))
    repo.append_message(session.id, MessageRole.USER, "hello")
    repo.append_message(
        session.id,
        MessageRole.ASSISTANT,
        "unfinished",
        status=MessageStatus.STOPPED,
        completion_marker=False,
    )
    request = PromptComposer("Be concise").compose(
        repo.list_messages(session.id),
        workspace=session.workspace_path,
        tools=[{"type": "function", "function": {"name": "read_file"}}],
    )
    database.close()
    assert request.messages[0]["role"] == "system"
    assert request.messages[0]["content"] == request.kernel
    assert request.messages[1] == {"role": "system", "content": "Be concise"}
    assert request.messages[2] == {"role": "user", "content": "hello"}
    assert "workspace" in request.messages[3]["content"]
    assert "unfinished" not in str(request.messages)
    assert request.tools[0]["function"]["name"] == "read_file"


def test_tool_call_protocol_is_reconstructed(tmp_path):
    database = Database(tmp_path / "agent.sqlite3")
    repo = Repository(database)
    session = repo.create_session("Draft", str(tmp_path / "workspace"))
    calls = [
        {"id": "call-1", "type": "function", "function": {"name": "read_file", "arguments": "{}"}}
    ]
    repo.append_message(session.id, MessageRole.ASSISTANT, "", tool_calls=calls)
    repo.append_message(session.id, MessageRole.TOOL, "result", tool_call_id="call-1")
    request = PromptComposer().compose(
        repo.list_messages(session.id), workspace=session.workspace_path
    )
    database.close()
    assert request.messages[1]["tool_calls"] == calls
    assert request.messages[2]["tool_call_id"] == "call-1"


def test_prompt_truncation_removes_complete_old_turns(tmp_path):
    database = Database(tmp_path / "agent.sqlite3")
    repo = Repository(database)
    session = repo.create_session("Draft", str(tmp_path / "workspace"))
    for index in range(3):
        repo.append_message(session.id, MessageRole.USER, f"question-{index}")
        repo.append_message(session.id, MessageRole.ASSISTANT, f"answer-{index}")
    request = PromptComposer().compose(
        repo.list_messages(session.id),
        workspace=session.workspace_path,
        context_limit=100,
        truncate=True,
    )
    database.close()
    contents = str(request.messages)
    assert request.truncated is True
    assert "question-0" not in contents
    assert "question-2" in contents
    assert "answer-2" in contents


def test_prompt_truncation_handles_mixed_turns_and_tool_history(tmp_path):
    database = Database(tmp_path / "agent.sqlite3")
    repo = Repository(database)
    session = repo.create_session("Draft", str(tmp_path / "workspace"))
    repo.append_message(session.id, MessageRole.USER, "第一轮短问题")
    repo.append_message(session.id, MessageRole.ASSISTANT, "第一轮短回答")
    calls = [
        {
            "id": "call-2",
            "type": "function",
            "function": {"name": "read_file", "arguments": '{"path":"notes.txt"}'},
        }
    ]
    repo.append_message(session.id, MessageRole.USER, "第二轮需要读取较长资料")
    repo.append_message(session.id, MessageRole.ASSISTANT, "", tool_calls=calls)
    repo.append_message(
        session.id, MessageRole.TOOL, "工具结果 " + ("资料 " * 80), tool_call_id="call-2"
    )
    repo.append_message(session.id, MessageRole.ASSISTANT, "第二轮已处理")
    repo.append_message(session.id, MessageRole.USER, "第三轮短问题")
    repo.append_message(session.id, MessageRole.ASSISTANT, "第三轮短回答")
    history = repo.list_messages(session.id)
    composer = PromptComposer()
    latest_two = composer.compose(history[2:], workspace=session.workspace_path)
    context_limit = int((latest_two.estimated_tokens + 5) / composer.INPUT_BUDGET_RATIO) + 1
    request = composer.compose(
        history,
        workspace=session.workspace_path,
        context_limit=context_limit,
        truncate=True,
    )
    database.close()
    contents = str(request.messages)
    assert request.truncated is True
    assert "第一轮短问题" not in contents
    assert "第二轮需要读取较长资料" in contents
    assert "工具结果" in contents
    assert "call-2" in contents
    assert "第三轮短问题" in contents
