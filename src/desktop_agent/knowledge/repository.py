from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Iterable, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from desktop_agent.knowledge.models import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_TOP_K_DENSE,
    DEFAULT_TOP_K_FUSION,
    DEFAULT_TOP_K_SPARSE,
    DEFAULT_TOP_M_FINAL,
    ChunkDraft,
    ChunkRecord,
    Document,
    DocumentStatus,
    KnowledgeBase,
    KnowledgeError,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS knowledge_bases (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    embedding_provider_id TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding_dim INTEGER NOT NULL,
    chunk_size INTEGER NOT NULL,
    chunk_overlap INTEGER NOT NULL,
    top_k_dense INTEGER NOT NULL,
    top_k_sparse INTEGER NOT NULL,
    top_k_fusion INTEGER NOT NULL,
    top_m_final INTEGER NOT NULL,
    retrieval_mode TEXT NOT NULL DEFAULT 'normal',
    index_version INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    kb_id TEXT NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    title TEXT NOT NULL,
    stored_path TEXT NOT NULL DEFAULT '',
    sha256 TEXT NOT NULL,
    byte_size INTEGER NOT NULL,
    status TEXT NOT NULL,
    error TEXT,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    indexed_at TEXT,
    UNIQUE (kb_id, sha256)
);
CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    kb_id TEXT NOT NULL,
    doc_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    text TEXT NOT NULL,
    embed_text TEXT NOT NULL,
    heading_path TEXT NOT NULL DEFAULT '',
    page INTEGER,
    char_start INTEGER NOT NULL DEFAULT 0,
    char_end INTEGER NOT NULL DEFAULT 0,
    token_count INTEGER NOT NULL DEFAULT 0,
    embedding BLOB NOT NULL,
    UNIQUE (doc_id, ordinal)
);
CREATE INDEX IF NOT EXISTS idx_chunks_kb ON chunks (kb_id);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks (doc_id);
"""

FTS_SCHEMA = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5("
    "text, chunk_id UNINDEXED, kb_id UNINDEXED, tokenize='{tokenizer}')"
)

_UPDATABLE_FIELDS = frozenset(
    {
        "description",
        "chunk_size",
        "chunk_overlap",
        "top_k_dense",
        "top_k_sparse",
        "top_k_fusion",
        "top_m_final",
        "retrieval_mode",
    }
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _id() -> str:
    return str(uuid.uuid4())


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _optional_timestamp(value: str | None) -> datetime | None:
    return _timestamp(value) if value else None


class KnowledgeRepository:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._db: sqlite3.Connection | None = None

    async def open(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.path)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode = WAL")
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.execute("PRAGMA busy_timeout = 5000")
        self._db.executescript(SCHEMA)
        self._create_fts()
        self._db.commit()

    async def close(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None

    def _create_fts(self) -> None:
        for tokenizer in ("trigram", "unicode61"):
            try:
                self._db.execute(FTS_SCHEMA.format(tokenizer=tokenizer))
                return
            except sqlite3.OperationalError:
                continue
        raise KnowledgeError("SQLite FTS5 is unavailable")

    @property
    def db(self) -> sqlite3.Connection:
        if self._db is None:
            raise KnowledgeError("KnowledgeRepository is not open")
        return self._db

    @asynccontextmanager
    async def _transaction(self):
        try:
            yield
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    async def create_knowledge_base(
        self,
        *,
        name: str,
        embedding_provider_id: str,
        embedding_model: str,
        embedding_dim: int,
        description: str = "",
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
        top_k_dense: int = DEFAULT_TOP_K_DENSE,
        top_k_sparse: int = DEFAULT_TOP_K_SPARSE,
        top_k_fusion: int = DEFAULT_TOP_K_FUSION,
        top_m_final: int = DEFAULT_TOP_M_FINAL,
        retrieval_mode: str = "normal",
    ) -> KnowledgeBase:
        name = name.strip()
        if not name:
            raise KnowledgeError("知识库名称不能为空")
        if not 128 <= chunk_size <= 2048:
            raise KnowledgeError("chunk_size 必须在 128 到 2048 之间")
        if not 0 <= chunk_overlap < chunk_size:
            raise KnowledgeError("chunk_overlap 必须小于 chunk_size")
        if embedding_dim <= 0:
            raise KnowledgeError("嵌入维度必须大于 0")
        now = _now()
        kb_id = str(uuid.uuid4())
        try:
            self.db.execute(
                "INSERT INTO knowledge_bases (id, name, description, embedding_provider_id, "
                "embedding_model, embedding_dim, chunk_size, chunk_overlap, top_k_dense, "
                "top_k_sparse, top_k_fusion, top_m_final, retrieval_mode, index_version, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)",
                (
                    kb_id,
                    name,
                    description.strip(),
                    embedding_provider_id,
                    embedding_model,
                    embedding_dim,
                    chunk_size,
                    chunk_overlap,
                    top_k_dense,
                    top_k_sparse,
                    top_k_fusion,
                    top_m_final,
                    retrieval_mode,
                    now,
                    now,
                ),
            )
            self.db.commit()
        except sqlite3.IntegrityError as error:
            raise KnowledgeError(f"知识库名称已存在：{name}") from error
        return await self.get_knowledge_base(kb_id)

    async def get_knowledge_base(self, kb_id: str) -> KnowledgeBase | None:
        cursor = self.db.execute("SELECT * FROM knowledge_bases WHERE id = ?", (kb_id,))
        row = cursor.fetchone()
        return self._knowledge_base(row) if row else None

    async def list_knowledge_bases(self) -> list[KnowledgeBase]:
        cursor = self.db.execute(
            "SELECT * FROM knowledge_bases ORDER BY created_at ASC, name ASC"
        )
        rows = cursor.fetchall()
        return [self._knowledge_base(row) for row in rows]

    async def update_knowledge_base(self, kb_id: str, **fields: Any) -> KnowledgeBase:
        unknown = set(fields) - _UPDATABLE_FIELDS
        if unknown:
            raise KnowledgeError(f"不支持修改的字段：{sorted(unknown)}")
        if fields:
            assignments = ", ".join(f"{field} = ?" for field in fields)
            self.db.execute(
                f"UPDATE knowledge_bases SET {assignments}, updated_at = ? WHERE id = ?",
                (*fields.values(), _now(), kb_id),
            )
            self.db.commit()
        kb = await self.get_knowledge_base(kb_id)
        if kb is None:
            raise KnowledgeError(f"知识库不存在：{kb_id}")
        return kb

    async def delete_knowledge_base(self, kb_id: str) -> None:
        async with self._transaction():
            self.db.execute("DELETE FROM chunks_fts WHERE kb_id = ?", (kb_id,))
            self.db.execute("DELETE FROM knowledge_bases WHERE id = ?", (kb_id,))

    async def add_document(
        self,
        *,
        kb_id: str,
        filename: str,
        title: str,
        sha256: str,
        byte_size: int,
        stored_path: str = "",
        status: DocumentStatus = DocumentStatus.PENDING,
    ) -> Document:
        doc_id = _id()
        now = _now()
        try:
            self.db.execute(
                "INSERT INTO documents (id, kb_id, filename, title, stored_path, sha256, "
                "byte_size, status, error, chunk_count, created_at, indexed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, 0, ?, NULL)",
                (
                    doc_id,
                    kb_id,
                    filename,
                    title,
                    stored_path,
                    sha256,
                    byte_size,
                    status.value,
                    now,
                ),
            )
            self.db.commit()
        except sqlite3.IntegrityError as error:
            raise KnowledgeError("相同内容的文档已存在") from error
        document = await self.get_document(doc_id)
        if document is None:
            raise KnowledgeError("文档创建失败")
        return document

    async def get_document(self, doc_id: str) -> Document | None:
        cursor = self.db.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        row = cursor.fetchone()
        return self._document(row) if row else None

    async def list_documents(self, kb_id: str) -> list[Document]:
        cursor = self.db.execute(
            "SELECT * FROM documents WHERE kb_id = ? ORDER BY created_at ASC", (kb_id,)
        )
        rows = cursor.fetchall()
        return [self._document(row) for row in rows]

    async def find_document_by_sha(self, kb_id: str, sha256: str) -> Document | None:
        cursor = self.db.execute(
            "SELECT * FROM documents WHERE kb_id = ? AND sha256 = ?", (kb_id, sha256)
        )
        row = cursor.fetchone()
        return self._document(row) if row else None

    async def update_document(
        self,
        doc_id: str,
        *,
        status: DocumentStatus | None = None,
        error: str | None = None,
        chunk_count: int | None = None,
        stored_path: str | None = None,
        indexed_at: datetime | None = None,
    ) -> Document:
        assignments = ["error = ?"]
        values: list[Any] = [error]
        if status is not None:
            assignments.append("status = ?")
            values.append(status.value)
        if chunk_count is not None:
            assignments.append("chunk_count = ?")
            values.append(chunk_count)
        if stored_path is not None:
            assignments.append("stored_path = ?")
            values.append(stored_path)
        if indexed_at is not None:
            assignments.append("indexed_at = ?")
            values.append(indexed_at.isoformat())
        self.db.execute(
            f"UPDATE documents SET {', '.join(assignments)} WHERE id = ?",
            (*values, doc_id),
        )
        self.db.commit()
        document = await self.get_document(doc_id)
        if document is None:
            raise KnowledgeError(f"文档不存在：{doc_id}")
        return document

    async def delete_document(self, doc_id: str) -> None:
        cursor = self.db.execute("SELECT kb_id FROM documents WHERE id = ?", (doc_id,))
        row = cursor.fetchone()
        if row is None:
            return
        kb_id = row["kb_id"]
        async with self._transaction():
            self.db.execute(
                "DELETE FROM chunks_fts WHERE chunk_id IN "
                "(SELECT id FROM chunks WHERE doc_id = ?)",
                (doc_id,),
            )
            self.db.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            self.db.execute(
                "UPDATE knowledge_bases SET index_version = index_version + 1, updated_at = ? "
                "WHERE id = ?",
                (_now(), kb_id),
            )

    async def replace_chunks(
        self,
        doc_id: str,
        chunks: Sequence[ChunkDraft],
        embeddings: Sequence[Sequence[float]],
    ) -> int:
        if len(chunks) != len(embeddings):
            raise KnowledgeError("分块数量与嵌入数量不一致")
        cursor = self.db.execute("SELECT kb_id FROM documents WHERE id = ?", (doc_id,))
        row = cursor.fetchone()
        if row is None:
            raise KnowledgeError(f"文档不存在：{doc_id}")
        kb_id = row["kb_id"]
        kb = await self.get_knowledge_base(kb_id)
        if kb is None:
            raise KnowledgeError(f"知识库不存在：{kb_id}")
        normalized: list[bytes] = []
        for vector in embeddings:
            array = np.asarray(vector, dtype=np.float32)
            if array.ndim != 1 or array.size != kb.embedding_dim:
                raise KnowledgeError(
                    f"嵌入维度不匹配：期望 {kb.embedding_dim}，实际 {array.size}"
                )
            norm = float(np.linalg.norm(array))
            if norm > 0:
                array = array / norm
            normalized.append(array.tobytes())
        async with self._transaction():
            self.db.execute(
                "DELETE FROM chunks_fts WHERE chunk_id IN "
                "(SELECT id FROM chunks WHERE doc_id = ?)",
                (doc_id,),
            )
            self.db.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
            for draft, blob in zip(chunks, normalized):
                chunk_id = _id()
                self.db.execute(
                    "INSERT INTO chunks (id, kb_id, doc_id, ordinal, text, embed_text, "
                    "heading_path, page, char_start, char_end, token_count, embedding) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        chunk_id,
                        kb_id,
                        doc_id,
                        draft.ordinal,
                        draft.text,
                        draft.embed_text,
                        draft.heading_path,
                        draft.page,
                        draft.char_start,
                        draft.char_end,
                        draft.token_count,
                        blob,
                    ),
                )
                self.db.execute(
                    "INSERT INTO chunks_fts (text, chunk_id, kb_id) VALUES (?, ?, ?)",
                    (draft.text, chunk_id, kb_id),
                )
            self.db.execute(
                "UPDATE documents SET chunk_count = ? WHERE id = ?", (len(chunks), doc_id)
            )
            self.db.execute(
                "UPDATE knowledge_bases SET index_version = index_version + 1, updated_at = ? "
                "WHERE id = ?",
                (_now(), kb_id),
            )
        return len(chunks)

    async def chunk_count(self, kb_id: str) -> int:
        cursor = self.db.execute("SELECT COUNT(*) AS total FROM chunks WHERE kb_id = ?", (kb_id,))
        row = cursor.fetchone()
        return int(row["total"]) if row else 0

    async def load_vectors(self, kb_id: str) -> tuple[list[str], np.ndarray]:
        cursor = self.db.execute(
            "SELECT id, embedding FROM chunks WHERE kb_id = ? ORDER BY doc_id, ordinal", (kb_id,)
        )
        rows = cursor.fetchall()
        if not rows:
            return [], np.empty((0, 0), dtype=np.float32)
        ids = [row["id"] for row in rows]
        matrix = np.stack(
            [np.frombuffer(row["embedding"], dtype=np.float32) for row in rows]
        )
        return ids, matrix

    async def search_fts(self, kb_id: str, match: str, limit: int) -> list[str]:
        cursor = self.db.execute(
            "SELECT chunk_id FROM chunks_fts WHERE chunks_fts MATCH ? AND kb_id = ? "
            "ORDER BY bm25(chunks_fts) LIMIT ?",
            (match, kb_id, limit),
        )
        rows = cursor.fetchall()
        return [row["chunk_id"] for row in rows]

    async def get_chunks(self, chunk_ids: Iterable[str]) -> dict[str, ChunkRecord]:
        ids = list(dict.fromkeys(chunk_ids))
        if not ids:
            return {}
        placeholders = ", ".join("?" for _ in ids)
        cursor = self.db.execute(
            "SELECT c.id, c.kb_id, c.doc_id, c.ordinal, c.text, c.heading_path, c.page, "
            "d.title AS doc_name, k.name AS kb_name "
            "FROM chunks c JOIN documents d ON d.id = c.doc_id "
            "JOIN knowledge_bases k ON k.id = c.kb_id "
            f"WHERE c.id IN ({placeholders})",
            ids,
        )
        rows = cursor.fetchall()
        return {
            row["id"]: ChunkRecord(
                id=row["id"],
                kb_id=row["kb_id"],
                kb_name=row["kb_name"],
                doc_id=row["doc_id"],
                doc_name=row["doc_name"],
                ordinal=row["ordinal"],
                text=row["text"],
                heading_path=row["heading_path"],
                page=row["page"],
            )
            for row in rows
        }

    @staticmethod
    def _knowledge_base(row: sqlite3.Row) -> KnowledgeBase:
        return KnowledgeBase(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            embedding_provider_id=row["embedding_provider_id"],
            embedding_model=row["embedding_model"],
            embedding_dim=row["embedding_dim"],
            chunk_size=row["chunk_size"],
            chunk_overlap=row["chunk_overlap"],
            top_k_dense=row["top_k_dense"],
            top_k_sparse=row["top_k_sparse"],
            top_k_fusion=row["top_k_fusion"],
            top_m_final=row["top_m_final"],
            retrieval_mode=row["retrieval_mode"],
            index_version=row["index_version"],
            created_at=_timestamp(row["created_at"]),
            updated_at=_timestamp(row["updated_at"]),
        )

    @staticmethod
    def _document(row: sqlite3.Row) -> Document:
        return Document(
            id=row["id"],
            kb_id=row["kb_id"],
            filename=row["filename"],
            title=row["title"],
            stored_path=row["stored_path"],
            sha256=row["sha256"],
            byte_size=row["byte_size"],
            status=DocumentStatus(row["status"]),
            error=row["error"],
            chunk_count=row["chunk_count"],
            created_at=_timestamp(row["created_at"]),
            indexed_at=_optional_timestamp(row["indexed_at"]),
        )
