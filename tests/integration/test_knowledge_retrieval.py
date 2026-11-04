from __future__ import annotations

import math
from collections.abc import Sequence

import pytest

from desktop_agent.knowledge.embedding import EmbeddingError
from desktop_agent.knowledge.index import build_fts_query
from desktop_agent.knowledge.indexer import DocumentIndexer
from desktop_agent.knowledge.models import (
    DocumentProcessingError,
    DocumentStatus,
    DuplicateDocumentError,
)
from desktop_agent.knowledge.repository import KnowledgeRepository
from desktop_agent.knowledge.retriever import RetrievalManager, format_retrieval_context


class BagOfCharsEmbedding:
    def __init__(self, dimension: int = 128):
        self.dimension = dimension
        self.calls = 0

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls += 1
        vectors = []
        for text in texts:
            vector = [0.0] * self.dimension
            for char in text:
                vector[ord(char) % self.dimension] += 1.0
            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            vectors.append([value / norm for value in vector])
        return vectors


class FailingEmbedding:
    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        raise EmbeddingError("服务不可用")


GUIDE = (
    "# 新人指南\n\n"
    "## 申请加入\n\n"
    "填写申请表并等待管理员审核。\n\n"
    "## 退出项目\n\n"
    "联系管理员删除权限。\n"
).encode()


async def open_repository(tmp_path):
    repository = KnowledgeRepository(tmp_path / "knowledge.sqlite3")
    await repository.open()
    return repository


@pytest.mark.asyncio
async def test_index_markdown_and_retrieve_with_citation(tmp_path):
    repository = await open_repository(tmp_path)
    try:
        kb = await repository.create_knowledge_base(
            name="指南",
            embedding_provider_id="provider",
            embedding_model="bag",
            embedding_dim=128,
            chunk_size=200,
            chunk_overlap=20,
        )
        embedding = BagOfCharsEmbedding(128)
        indexer = DocumentIndexer(repository, embedding, tmp_path / "knowledge")
        document = await indexer.index_bytes(kb.id, "guide.md", GUIDE, title="新人指南")
        assert document.status is DocumentStatus.READY
        assert document.chunk_count >= 2

        retriever = RetrievalManager(repository, embedding, similarity_threshold=0.05)
        result = await retriever.retrieve([kb.id], "怎么申请加入项目")
        assert result.hits
        top = result.hits[0]
        assert "申请" in top.text
        assert top.doc_name == "新人指南"
        assert top.heading_path == "新人指南 / 申请加入"
        context = format_retrieval_context(result)
        assert "[1] 来源：" in context
        assert "不要编造" in context
        payload = result.as_payload()
        assert payload["hits"][0]["doc_name"] == "新人指南"
    finally:
        await repository.close()


@pytest.mark.asyncio
async def test_duplicate_document_is_rejected(tmp_path):
    repository = await open_repository(tmp_path)
    try:
        kb = await repository.create_knowledge_base(
            name="指南",
            embedding_provider_id="provider",
            embedding_model="bag",
            embedding_dim=128,
        )
        indexer = DocumentIndexer(repository, BagOfCharsEmbedding(128), tmp_path / "knowledge")
        await indexer.index_bytes(kb.id, "guide.md", GUIDE)
        with pytest.raises(DuplicateDocumentError):
            await indexer.index_bytes(kb.id, "guide.md", GUIDE)
    finally:
        await repository.close()


@pytest.mark.asyncio
async def test_new_document_is_visible_after_indexing(tmp_path):
    repository = await open_repository(tmp_path)
    try:
        kb = await repository.create_knowledge_base(
            name="指南",
            embedding_provider_id="provider",
            embedding_model="bag",
            embedding_dim=128,
        )
        embedding = BagOfCharsEmbedding(128)
        indexer = DocumentIndexer(repository, embedding, tmp_path / "knowledge")
        await indexer.index_bytes(kb.id, "guide.md", GUIDE, title="新人指南")
        retriever = RetrievalManager(repository, embedding, similarity_threshold=0.05)
        await retriever.retrieve([kb.id], "如何反馈问题")

        await indexer.index_bytes(
            kb.id,
            "faq.md",
            "## 常见问题\n\n如何反馈问题？发送邮件给管理员。".encode(),
            title="FAQ",
        )
        result = await retriever.retrieve([kb.id], "如何反馈问题")
        assert any("反馈" in hit.text for hit in result.hits)
    finally:
        await repository.close()


@pytest.mark.asyncio
async def test_retrieval_without_knowledge_bases(tmp_path):
    repository = await open_repository(tmp_path)
    try:
        retriever = RetrievalManager(repository, BagOfCharsEmbedding(128))
        result = await retriever.retrieve([], "任意问题")
        assert result.hits == ()
    finally:
        await repository.close()


@pytest.mark.asyncio
async def test_indexing_failure_marks_document_failed(tmp_path):
    repository = await open_repository(tmp_path)
    try:
        kb = await repository.create_knowledge_base(
            name="指南",
            embedding_provider_id="provider",
            embedding_model="bag",
            embedding_dim=128,
        )
        indexer = DocumentIndexer(repository, FailingEmbedding(), tmp_path / "knowledge")
        with pytest.raises(DocumentProcessingError):
            await indexer.index_bytes(kb.id, "guide.md", GUIDE)
        documents = await repository.list_documents(kb.id)
        assert documents[0].status is DocumentStatus.FAILED
        assert documents[0].error
    finally:
        await repository.close()


def test_build_fts_query_uses_trigrams_for_chinese():
    query = build_fts_query("怎么申请加入项目")
    assert '"怎么申"' in query
    assert '"申请加"' in query
    assert " OR " in query


def test_build_fts_query_keeps_english_words():
    query = build_fts_query("how to install vector database")
    assert '"install"' in query
    assert '"vector"' in query
