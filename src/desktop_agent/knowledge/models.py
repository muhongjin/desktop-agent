from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 50
DEFAULT_TOP_K_DENSE = 50
DEFAULT_TOP_K_SPARSE = 50
DEFAULT_TOP_K_FUSION = 20
DEFAULT_TOP_M_FINAL = 5
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_CHUNKS_PER_KB = 500_000


class KnowledgeError(Exception):
    pass


class DocumentProcessingError(KnowledgeError):
    pass


class DuplicateDocumentError(KnowledgeError):
    pass


class DocumentStatus(StrEnum):
    PENDING = "pending"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ParsedSection:
    text: str
    heading_path: str = ""
    page: int | None = None


@dataclass(frozen=True, slots=True)
class KnowledgeBase:
    id: str
    name: str
    description: str
    embedding_provider_id: str
    embedding_model: str
    embedding_dim: int
    chunk_size: int
    chunk_overlap: int
    top_k_dense: int
    top_k_sparse: int
    top_k_fusion: int
    top_m_final: int
    retrieval_mode: str
    index_version: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class Document:
    id: str
    kb_id: str
    filename: str
    title: str
    stored_path: str
    sha256: str
    byte_size: int
    status: DocumentStatus
    error: str | None
    chunk_count: int
    created_at: datetime
    indexed_at: datetime | None


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    ordinal: int
    text: str
    embed_text: str
    heading_path: str
    page: int | None
    char_start: int
    char_end: int
    token_count: int


@dataclass(frozen=True, slots=True)
class ChunkRecord:
    id: str
    kb_id: str
    kb_name: str
    doc_id: str
    doc_name: str
    ordinal: int
    text: str
    heading_path: str
    page: int | None


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    chunk_id: str
    kb_id: str
    kb_name: str
    doc_id: str
    doc_name: str
    text: str
    heading_path: str
    page: int | None
    ordinal: int
    score: float
    similarity: float


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    query: str
    hits: tuple[RetrievalHit, ...]
    elapsed_ms: int
    total_candidates: int = 0
    truncated: bool = False

    def as_payload(self) -> dict:
        return {
            "query": self.query,
            "elapsed_ms": self.elapsed_ms,
            "truncated": self.truncated,
            "hits": [
                {
                    "n": index,
                    "kb_id": hit.kb_id,
                    "kb_name": hit.kb_name,
                    "doc_id": hit.doc_id,
                    "doc_name": hit.doc_name,
                    "heading": hit.heading_path,
                    "page": hit.page,
                    "score": round(hit.score, 6),
                    "similarity": round(hit.similarity, 6),
                    "snippet": hit.text[:300],
                }
                for index, hit in enumerate(self.hits, start=1)
            ],
        }
