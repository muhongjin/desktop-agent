from __future__ import annotations

import asyncio
import hashlib
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from desktop_agent.knowledge.chunker import RecursiveCharacterChunker
from desktop_agent.knowledge.embedding import EmbeddingClient, EmbeddingError
from desktop_agent.knowledge.models import (
    MAX_FILE_BYTES,
    Document,
    DocumentProcessingError,
    DocumentStatus,
    DuplicateDocumentError,
    KnowledgeError,
)
from desktop_agent.knowledge.parsers import parse_bytes
from desktop_agent.knowledge.repository import KnowledgeRepository

ProgressCallback = Callable[[int, int], None]

_UNSAFE_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _safe_filename(name: str) -> str:
    cleaned = _UNSAFE_FILENAME.sub("_", Path(name).name).strip(". ")
    return cleaned or "document"


class DocumentIndexer:
    def __init__(
        self,
        repository: KnowledgeRepository,
        embedding_client: EmbeddingClient,
        storage_root: str | Path,
        *,
        batch_size: int = 32,
        max_file_bytes: int = MAX_FILE_BYTES,
    ):
        self.repository = repository
        self.embedding_client = embedding_client
        self.storage_root = Path(storage_root)
        self.batch_size = max(1, batch_size)
        self.max_file_bytes = max_file_bytes

    async def index_file(
        self,
        kb_id: str,
        source_path: str | Path,
        *,
        title: str | None = None,
        progress: ProgressCallback | None = None,
    ) -> Document:
        path = Path(source_path)
        try:
            data = await asyncio.to_thread(path.read_bytes)
        except OSError as error:
            raise DocumentProcessingError(f"读取文件失败：{error}") from error
        return await self.index_bytes(kb_id, path.name, data, title=title, progress=progress)

    async def index_bytes(
        self,
        kb_id: str,
        filename: str,
        data: bytes,
        *,
        title: str | None = None,
        progress: ProgressCallback | None = None,
    ) -> Document:
        if not data:
            raise DocumentProcessingError("文件为空")
        if len(data) > self.max_file_bytes:
            raise DocumentProcessingError(
                f"文件超过大小限制（{self.max_file_bytes // (1024 * 1024)} MB）"
            )
        kb = await self.repository.get_knowledge_base(kb_id)
        if kb is None:
            raise KnowledgeError(f"知识库不存在：{kb_id}")
        sha256 = hashlib.sha256(data).hexdigest()
        existing = await self.repository.find_document_by_sha(kb_id, sha256)
        if existing is not None:
            raise DuplicateDocumentError(f"相同内容的文档已存在：{existing.filename}")
        title_text = (title or Path(filename).stem).strip() or Path(filename).stem
        document = await self.repository.add_document(
            kb_id=kb_id,
            filename=filename,
            title=title_text,
            sha256=sha256,
            byte_size=len(data),
        )
        await self.repository.update_document(
            document.id, status=DocumentStatus.INDEXING, error=None
        )
        try:
            stored_path = await asyncio.to_thread(
                self._store_copy, kb_id, document.id, filename, data
            )
            await self.repository.update_document(document.id, stored_path=str(stored_path))
            sections = await asyncio.to_thread(parse_bytes, filename, data)
            chunker = RecursiveCharacterChunker(kb.chunk_size, kb.chunk_overlap)
            drafts = chunker.split_sections(title_text, sections)
            if not drafts:
                raise DocumentProcessingError("文档没有可索引的内容")
            embeddings: list[list[float]] = []
            total = len(drafts)
            for start in range(0, total, self.batch_size):
                batch = drafts[start : start + self.batch_size]
                try:
                    vectors = await self.embedding_client.embed(
                        [draft.embed_text for draft in batch]
                    )
                except EmbeddingError as error:
                    raise DocumentProcessingError(str(error)) from error
                if len(vectors) != len(batch):
                    raise DocumentProcessingError("嵌入返回数量与分块数量不一致")
                embeddings.extend(vectors)
                if progress is not None:
                    progress(min(start + len(batch), total), total)
            await self.repository.replace_chunks(document.id, drafts, embeddings)
            return await self.repository.update_document(
                document.id,
                status=DocumentStatus.READY,
                chunk_count=len(drafts),
                indexed_at=datetime.now(UTC),
                error=None,
            )
        except Exception as error:
            message = str(error) or type(error).__name__
            await self.repository.update_document(
                document.id, status=DocumentStatus.FAILED, error=message
            )
            if isinstance(error, KnowledgeError):
                raise
            raise DocumentProcessingError(f"索引失败：{message}") from error

    async def delete_document(self, doc_id: str) -> None:
        document = await self.repository.get_document(doc_id)
        if document is None:
            return
        await self.repository.delete_document(doc_id)
        if document.stored_path:
            path = Path(document.stored_path)
            if path.is_file():
                try:
                    await asyncio.to_thread(path.unlink)
                except OSError:
                    pass

    def _store_copy(
        self, kb_id: str, doc_id: str, filename: str, data: bytes
    ) -> Path:
        target_dir = self.storage_root / kb_id / "docs"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{doc_id}-{_safe_filename(filename)}"
        target.write_bytes(data)
        return target
