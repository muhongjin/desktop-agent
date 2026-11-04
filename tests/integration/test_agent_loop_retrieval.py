from __future__ import annotations

import pytest

from desktop_agent.agent.loop import AgentLoop, RetrievalOutcome
from desktop_agent.agent.prompt import PromptComposer
from desktop_agent.domain.models import MessageRole
from desktop_agent.providers.openai_compatible import AssistantTurn, TextDelta
from desktop_agent.security.permissions import PermissionBroker, SessionAccess
from desktop_agent.storage.database import Database
from desktop_agent.storage.repositories import Repository
from desktop_agent.tools.files import FileTools
from desktop_agent.tools.registry import file_tool_registry


class SequenceProvider:
    def __init__(self, turns):
        self.turns = list(turns)
        self.requests = []

    async def stream_chat(self, **request):
        self.requests.append(request)
        turn = self.turns.pop(0)
        for event in turn:
            yield event


class FakeRetrievalProvider:
    def __init__(self, outcome=None, error: Exception | None = None):
        self.outcome = outcome
        self.error = error
        self.calls = []

    async def retrieve(self, session_id: str, query: str):
        self.calls.append((session_id, query))
        if self.error is not None:
            raise self.error
        return self.outcome


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


async def collect(loop, session_id, content, access):
    return [
        event
        async for event in loop.send_message(
            session_id,
            content,
            model_id="deepseek-chat",
            thinking_strength=None,
            access=access,
        )
    ]


@pytest.mark.asyncio
async def test_loop_injects_retrieval_context_and_emits_event(loop_context):
    _, repo, session, access, broker, registry = loop_context
    provider = SequenceProvider([[TextDelta("答案"), AssistantTurn("答案", (), "stop")]])
    outcome = RetrievalOutcome(
        context="[1] 来源：新人指南\n申请加入项目的步骤",
        payload={"query": "怎么申请", "hits": [{"n": 1, "doc_name": "新人指南"}]},
    )
    retriever = FakeRetrievalProvider(outcome)
    loop = AgentLoop(
        repo,
        PromptComposer(),
        provider,
        broker,
        registry,
        retrieval_provider=retriever,
    )
    events = await collect(loop, session.id, "怎么申请", access)
    types = [event.type for event in events]
    assert types == ["turn_started", "retrieval", "text_delta", "turn_finished"]
    assert retriever.calls == [(session.id, "怎么申请")]
    messages = provider.requests[0]["messages"]
    assert any(message["content"] == outcome.context for message in messages)
    retrieval_event = next(event for event in events if event.type == "retrieval")
    assert retrieval_event.data["payload"]["query"] == "怎么申请"


@pytest.mark.asyncio
async def test_loop_degrades_when_retrieval_fails(loop_context):
    _, repo, session, access, broker, registry = loop_context
    provider = SequenceProvider([[TextDelta("普通回答"), AssistantTurn("普通回答", (), "stop")]])
    retriever = FakeRetrievalProvider(error=RuntimeError("embedding down"))
    loop = AgentLoop(
        repo,
        PromptComposer(),
        provider,
        broker,
        registry,
        retrieval_provider=retriever,
    )
    events = await collect(loop, session.id, "你好", access)
    assert [event.type for event in events] == [
        "turn_started",
        "retrieval_failed",
        "text_delta",
        "turn_finished",
    ]
    messages = provider.requests[0]["messages"]
    assert all("embedding down" not in message["content"] for message in messages)
    assert repo.list_messages(session.id)[-1].content == "普通回答"


@pytest.mark.asyncio
async def test_retrieval_runs_only_on_first_turn(loop_context):
    _, repo, session, access, broker, registry = loop_context
    provider = SequenceProvider(
        [
            [
                TextDelta(""),
                AssistantTurn(
                    "",
                    (),
                    "stop",
                ),
            ]
        ]
    )
    retriever = FakeRetrievalProvider(RetrievalOutcome(context="资料", payload={"hits": []}))
    loop = AgentLoop(
        repo,
        PromptComposer(),
        provider,
        broker,
        registry,
        retrieval_provider=retriever,
    )
    await collect(loop, session.id, "第一句", access)
    assert len(retriever.calls) == 1
    messages = repo.list_messages(session.id)
    assert messages[0].role is MessageRole.USER
