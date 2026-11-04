from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from PySide6.QtCore import QObject, Signal

from desktop_agent.chat_service import ChatService
from desktop_agent.domain.models import ProviderConfig
from desktop_agent.knowledge.models import RetrievalHit, RetrievalResult
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
        yield TextDelta("答案")
        yield AssistantTurn("答案", (), "stop")

    async def close(self):
        self.closed = True


class FakeKnowledge:
    def __init__(self):
        self.queries = []

    def kb_ids_for_session(self, session_id):
        return ["kb-1"]

    async def retrieve(self, kb_ids, query):
        self.queries.append((list(kb_ids), query))
        return RetrievalResult(
            query=query,
            hits=(
                RetrievalHit(
                    chunk_id="chunk-1",
                    kb_id="kb-1",
                    kb_name="指南",
                    doc_id="doc-1",
                    doc_name="新人指南",
                    text="申请加入项目的步骤",
                    heading_path="申请加入",
                    page=None,
                    ordinal=0,
                    score=0.9,
                    similarity=0.8,
                ),
            ),
            elapsed_ms=5,
        )


def prepare(tmp_path):
    database = Database(tmp_path / "agent.sqlite3")
    repository = Repository(database)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    session = repository.create_session(
        "Draft", str(workspace), current_model_id="openai:model-a"
    )
    now = datetime.now(UTC)
    repository.set_provider_config(
        ProviderConfig(
            "openai", "OpenAI", "https://example.test/v1", {"models": ["model-a"]}, now, now
        )
    )
    return database, repository, session


@pytest.mark.asyncio
async def test_chat_service_injects_retrieval_and_persists_citations(tmp_path):
    database, repository, session = prepare(tmp_path)
    provider = Provider()
    knowledge = FakeKnowledge()
    service = ChatService(
        repository,
        Sessions(session.id),
        None,
        Settings(),
        PermissionBroker(),
        Credentials(),
        safe_mode=False,
        provider_factory=lambda base_url, api_key: provider,
        knowledge=knowledge,
    )
    service.sendMessage("怎么申请加入")
    while service.running:
        await asyncio.sleep(0.01)
    assert knowledge.queries == [(["kb-1"], "怎么申请加入")]
    request = provider.requests[0]
    assert any("申请加入项目的步骤" in message["content"] for message in request["messages"])
    assistant = repository.list_messages(session.id)[-1]
    assert assistant.retrieval["hits"][0]["doc_name"] == "新人指南"
    row = service.messageModel.rowCount() - 1
    retrieval = service.messageModel.data(
        service.messageModel.index(row, 0), service.messageModel.RetrievalRole
    )
    assert "新人指南" in retrieval
    database.close()


@pytest.mark.asyncio
async def test_safe_mode_skips_knowledge_retrieval(tmp_path):
    database, repository, session = prepare(tmp_path)
    provider = Provider()
    knowledge = FakeKnowledge()
    service = ChatService(
        repository,
        Sessions(session.id),
        None,
        Settings(),
        PermissionBroker(),
        Credentials(),
        safe_mode=True,
        provider_factory=lambda base_url, api_key: provider,
        knowledge=knowledge,
    )
    service.sendMessage("怎么申请加入")
    while service.running:
        await asyncio.sleep(0.01)
    assert knowledge.queries == []
    request = provider.requests[0]
    assert all("申请加入项目的步骤" not in message["content"] for message in request["messages"])
    database.close()
