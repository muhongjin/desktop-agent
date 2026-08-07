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
    calls = [{"id": "call-1", "type": "function", "function": {"name": "read_file", "arguments": "{}"}}]
    repo.append_message(session.id, MessageRole.ASSISTANT, "", tool_calls=calls)
    repo.append_message(session.id, MessageRole.TOOL, "result", tool_call_id="call-1")
    request = PromptComposer().compose(repo.list_messages(session.id), workspace=session.workspace_path)
    database.close()
    assert request.messages[1]["tool_calls"] == calls
    assert request.messages[2]["tool_call_id"] == "call-1"
