from __future__ import annotations

import pytest

from desktop_agent.knowledge.models import DuplicateDocumentError, KnowledgeError
from desktop_agent.knowledge.repository import KnowledgeRepository
from desktop_agent.knowledge.service import KnowledgeService
from desktop_agent.storage.database import Database
from desktop_agent.storage.repositories import Repository


class FakeEmbedding:
    async def embed(self, texts):
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]

    async def probe_dimension(self, sample: str = "dimension probe") -> int:
        return 4


async def fake_factory(provider_id: str, model_id: str):
    return FakeEmbedding()


@pytest.mark.asyncio
async def test_create_import_retrieve_and_delete(tmp_path):
    database = Database(tmp_path / "agent.sqlite3")
    repository = Repository(database)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    session = repository.create_session("聊天", str(workspace))
    service = KnowledgeService(
        KnowledgeRepository(tmp_path / "knowledge.sqlite3"),
        repository,
        fake_factory,
        tmp_path,
    )
    await service.start()
    try:
        assert service.knowledgeBases.rowCount() == 0
        kb = await service.create_knowledge_base(
            "指南", "新人手册", "provider", "model", embedding_dim=4
        )
        assert service.knowledgeBases.rowCount() == 1
        assert service.currentKnowledgeBaseId == kb.id

        guide = tmp_path / "guide.md"
        guide.write_text("# 新人指南\n\n## 申请加入\n\n填写申请表并等待审核。", encoding="utf-8")
        documents = await service.import_files(kb.id, [str(guide)])
        assert documents[0].chunk_count >= 1
        assert service.documents.rowCount() == 1

        result = await service.retrieve([kb.id], "怎么申请加入")
        assert result.hits
        assert result.hits[0].doc_name == "guide"

        repository.set_session_knowledge_bases(session.id, [kb.id])
        assert service.kb_ids_for_session(session.id) == [kb.id]

        await service.delete_document(kb.id, documents[0].id)
        assert service.documents.rowCount() == 0

        await service.delete_knowledge_base(kb.id)
        assert service.knowledgeBases.rowCount() == 0
    finally:
        await service.stop()
        database.close()


@pytest.mark.asyncio
async def test_duplicate_import_is_reported(tmp_path):
    database = Database(tmp_path / "agent.sqlite3")
    repository = Repository(database)
    service = KnowledgeService(
        KnowledgeRepository(tmp_path / "knowledge.sqlite3"),
        repository,
        fake_factory,
        tmp_path,
    )
    await service.start()
    try:
        kb = await service.create_knowledge_base("指南", "", "provider", "model", embedding_dim=4)
        guide = tmp_path / "guide.md"
        guide.write_text("内容", encoding="utf-8")
        await service.import_files(kb.id, [str(guide)])
        with pytest.raises(DuplicateDocumentError):
            await service.import_files(kb.id, [str(guide)])
    finally:
        await service.stop()
        database.close()


@pytest.mark.asyncio
async def test_update_knowledge_base_settings(tmp_path):
    database = Database(tmp_path / "agent.sqlite3")
    repository = Repository(database)
    service = KnowledgeService(
        KnowledgeRepository(tmp_path / "knowledge.sqlite3"),
        repository,
        fake_factory,
        tmp_path,
    )
    await service.start()
    try:
        kb = await service.create_knowledge_base("指南", "", "provider", "model", embedding_dim=4)
        assert service.knowledgeBaseSettings(kb.id) == {
            "chunkSize": 512,
            "chunkOverlap": 50,
            "topMFinal": 5,
        }
        await service.update_knowledge_base_settings(kb.id, 800, 80, 8)
        assert service.knowledgeBaseSettings(kb.id) == {
            "chunkSize": 800,
            "chunkOverlap": 80,
            "topMFinal": 8,
        }
        refreshed = await service.repository.get_knowledge_base(kb.id)
        assert (refreshed.chunk_size, refreshed.chunk_overlap, refreshed.top_m_final) == (
            800,
            80,
            8,
        )
        with pytest.raises(KnowledgeError):
            await service.update_knowledge_base_settings(kb.id, 512, 900, 5)
        with pytest.raises(KnowledgeError):
            await service.update_knowledge_base_settings(kb.id, 512, 50, 0)
    finally:
        await service.stop()
        database.close()