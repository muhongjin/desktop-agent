from desktop_agent.knowledge.chunker import RecursiveCharacterChunker, estimate_tokens
from desktop_agent.knowledge.embedding import (
    EmbeddingClient,
    EmbeddingError,
    OpenAICompatibleEmbedding,
)
from desktop_agent.knowledge.index import build_fts_query
from desktop_agent.knowledge.indexer import DocumentIndexer, ProgressCallback
from desktop_agent.knowledge.models import (
    ChunkDraft,
    ChunkRecord,
    Document,
    DocumentProcessingError,
    DocumentStatus,
    DuplicateDocumentError,
    KnowledgeBase,
    KnowledgeError,
    ParsedSection,
    RetrievalHit,
    RetrievalResult,
)
from desktop_agent.knowledge.repository import KnowledgeRepository
from desktop_agent.knowledge.retriever import (
    RetrievalError,
    RetrievalManager,
    format_retrieval_context,
)

__all__ = [
    "ChunkDraft",
    "ChunkRecord",
    "Document",
    "DocumentIndexer",
    "DocumentProcessingError",
    "DocumentStatus",
    "DuplicateDocumentError",
    "EmbeddingClient",
    "EmbeddingError",
    "KnowledgeBase",
    "KnowledgeError",
    "KnowledgeRepository",
    "OpenAICompatibleEmbedding",
    "ParsedSection",
    "ProgressCallback",
    "RecursiveCharacterChunker",
    "RetrievalError",
    "RetrievalHit",
    "RetrievalManager",
    "RetrievalResult",
    "build_fts_query",
    "estimate_tokens",
    "format_retrieval_context",
]
