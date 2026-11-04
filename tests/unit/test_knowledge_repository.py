from __future__ import annotations

from contextlib import asynccontextmanager

import numpy as np
import pytest

from desktop_agent.knowledge.models import ChunkDraft, KnowledgeError
from desktop_agent.knowledge.repository import KnowledgeRepository


@asynccontextmanager
async def open_repository(tmp_path):
    repository = KnowledgeRepository(tmp_path / "knowledge.sqlite3")
    await repository.open()
    try:
        yield repository
    finally:
        await repository.close()


async def create_kb(repository, **overrides):
    values = {
        "name": "手册",
        "embedding_provider_id": "provider",
        "embedding_model": "bge-m3",
        "embedding_dim": 4,
    }
    values.update(overrides)
    return await repository.create_knowledge_base(**values)


def make_draft(ordinal: int, text: str) -> ChunkDraft:
    return ChunkDraft(
        ordinal=ordinal,
        text=text,
        embed_text=f"手册\n{text}",
        heading_path="",
        page=None,
        char_start=0,
        char_end=len(text),
        token_count=len(text),
    )


@pytest.mark.asyncio
async def test_create_update_and_list_knowledge_bases(tmp_path):
    async with open_repository(tmp_path) as repository:
        kb = await create_kb(repository)
        assert kb.name == "手册"
        assert kb.index_version == 0
        updated = await repository.update_knowledge_base(kb.id, top_m_final=3)
        assert updated.top_m_final == 3
        assert [item.id for item in await repository.list_knowledge_bases()] == [kb.id]


@pytest.mark.asyncio
async def test_duplicate_knowledge_base_name_is_rejected(tmp_path):
    async with open_repository(tmp_path) as repository:
        await create_kb(repository)
        with pytest.raises(KnowledgeError):
            await create_kb(repository)


@pytest.mark.asyncio
async def test_chunks_fts_and_normalized_vectors(tmp_path):
    async with open_repository(tmp_path) as repository:
        kb = await create_kb(repository)
        document = await repository.add_document(
            kb_id=kb.id, filename="a.md", title="新人指南", sha256="sha", byte_size=10
        )
        drafts = [make_draft(0, "申请加入项目的步骤"), make_draft(1, "退出项目的流程")]
        await repository.replace_chunks(
            document.id, drafts, [[3.0, 4.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0]]
        )

        chunk_ids = await repository.search_fts(kb.id, '"申请加"', 10)
        assert len(chunk_ids) == 1
        records = await repository.get_chunks(chunk_ids)
        assert records[chunk_ids[0]].doc_name == "新人指南"
        assert records[chunk_ids[0]].kb_name == "手册"

        ids, matrix = await repository.load_vectors(kb.id)
        assert len(ids) == 2
        assert matrix.shape == (2, 4)
        assert np.allclose(np.linalg.norm(matrix, axis=1), 1.0)

        refreshed = await repository.get_knowledge_base(kb.id)
        assert refreshed is not None and refreshed.index_version == 1
        assert await repository.chunk_count(kb.id) == 2


@pytest.mark.asyncio
async def test_dimension_mismatch_is_rejected(tmp_path):
    async with open_repository(tmp_path) as repository:
        kb = await create_kb(repository)
        document = await repository.add_document(
            kb_id=kb.id, filename="a.md", title="t", sha256="sha2", byte_size=1
        )
        with pytest.raises(KnowledgeError):
            await repository.replace_chunks(document.id, [make_draft(0, "内容")], [[1.0, 0.0]])


@pytest.mark.asyncio
async def test_delete_document_removes_chunks_and_bumps_version(tmp_path):
    async with open_repository(tmp_path) as repository:
        kb = await create_kb(repository)
        document = await repository.add_document(
            kb_id=kb.id, filename="a.md", title="t", sha256="sha3", byte_size=1
        )
        await repository.replace_chunks(document.id, [make_draft(0, "申请加入项目")], [[1.0, 0, 0, 0]])
        await repository.delete_document(document.id)
        assert await repository.chunk_count(kb.id) == 0
        assert await repository.search_fts(kb.id, '"申请加"', 5) == []
        refreshed = await repository.get_knowledge_base(kb.id)
        assert refreshed is not None and refreshed.index_version == 2


@pytest.mark.asyncio
async def test_delete_knowledge_base_clears_everything(tmp_path):
    async with open_repository(tmp_path) as repository:
        kb = await create_kb(repository)
        document = await repository.add_document(
            kb_id=kb.id, filename="a.md", title="t", sha256="sha4", byte_size=1
        )
        await repository.replace_chunks(document.id, [make_draft(0, "申请加入项目")], [[1.0, 0, 0, 0]])
        await repository.delete_knowledge_base(kb.id)
        assert await repository.list_knowledge_bases() == []
        assert await repository.list_documents(kb.id) == []
        assert await repository.search_fts(kb.id, '"申请加"', 5) == []
