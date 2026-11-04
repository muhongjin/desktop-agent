from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path

from PySide6.QtCore import Property, QAbstractListModel, QModelIndex, QObject, Qt, Signal, Slot
from PySide6.QtWidgets import QFileDialog

from desktop_agent.knowledge.embedding import EmbeddingClient, EmbeddingError
from desktop_agent.knowledge.indexer import DocumentIndexer, ProgressCallback
from desktop_agent.knowledge.models import (
    Document,
    KnowledgeBase,
    KnowledgeError,
    RetrievalResult,
)
from desktop_agent.knowledge.repository import KnowledgeRepository
from desktop_agent.knowledge.retriever import RetrievalError, RetrievalManager

EmbeddingFactory = Callable[[str, str], Awaitable[EmbeddingClient]]
ModelLister = Callable[[str], Awaitable[list[str]]]

_EMBEDDING_MARKERS = (
    "embed",
    "bge",
    "nomic",
    "m3e",
    "bce-embedding",
    "gte",
    "jina",
    "voyage",
    "e5-",
    "e5_",
    "multilingual-e5",
)

_EMBEDDING_PRESETS = {
    "openai": ["text-embedding-3-small", "text-embedding-3-large"],
    "siliconflow": [
        "BAAI/bge-m3",
        "BAAI/bge-large-zh-v1.5",
        "netease-youdao/bce-embedding-base_v1",
    ],
    "ollama": ["nomic-embed-text", "bge-m3"],
    "bailian": ["text-embedding-v4", "text-embedding-v3"],
    "zhipu": ["embedding-3"],
    "gemini": ["gemini-embedding-001"],
}


def _embedding_like(name: str) -> bool:
    lowered = name.lower()
    if "rerank" in lowered:
        return False
    return any(marker in lowered for marker in _EMBEDDING_MARKERS)


def _embedding_options(provider_type: str, discovered: Sequence[str]) -> list[dict]:
    preferred = [name for name in discovered if _embedding_like(name)]
    if preferred:
        return [{"modelId": name} for name in preferred]
    presets = _EMBEDDING_PRESETS.get(provider_type, [])
    if presets:
        return [{"modelId": name} for name in presets]
    return []


IMPORT_FILTER = (
    "支持的文件 (*.txt *.md *.markdown *.pdf *.docx *.xlsx);;"
    "文本 (*.txt *.md *.markdown);;PDF (*.pdf);;Word (*.docx);;Excel (*.xlsx)"
)


class KnowledgeBaseListModel(QAbstractListModel):
    IdRole = Qt.UserRole + 1
    NameRole = Qt.UserRole + 2
    DescriptionRole = Qt.UserRole + 3
    DocumentCountRole = Qt.UserRole + 4
    ChunkCountRole = Qt.UserRole + 5
    EmbeddingModelRole = Qt.UserRole + 6
    ChunkSizeRole = Qt.UserRole + 7
    ChunkOverlapRole = Qt.UserRole + 8
    TopMFinalRole = Qt.UserRole + 9

    def __init__(self):
        super().__init__()
        self.rows: list[dict] = []

    def roleNames(self):
        return {
            self.IdRole: b"kbId",
            self.NameRole: b"name",
            self.DescriptionRole: b"description",
            self.DocumentCountRole: b"documentCount",
            self.ChunkCountRole: b"chunkCount",
            self.EmbeddingModelRole: b"embeddingModel",
            self.ChunkSizeRole: b"chunkSize",
            self.ChunkOverlapRole: b"chunkOverlap",
            self.TopMFinalRole: b"topMFinal",
        }

    def rowCount(self, parent=None):
        parent = parent or QModelIndex()
        return 0 if parent.isValid() else len(self.rows)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.rows):
            return None
        row = self.rows[index.row()]
        if role == self.IdRole:
            return row["kb_id"]
        if role == self.NameRole:
            return row["name"]
        if role == self.DescriptionRole:
            return row["description"]
        if role == self.DocumentCountRole:
            return row["document_count"]
        if role == self.ChunkCountRole:
            return row["chunk_count"]
        if role == self.EmbeddingModelRole:
            return row["embedding_model"]
        if role == self.ChunkSizeRole:
            return row.get("chunk_size", 512)
        if role == self.ChunkOverlapRole:
            return row.get("chunk_overlap", 50)
        if role == self.TopMFinalRole:
            return row.get("top_m_final", 5)
        if role == Qt.DisplayRole:
            return row["name"]
        return None

    def refresh(self, rows: list[dict]) -> None:
        self.beginResetModel()
        self.rows = list(rows)
        self.endResetModel()

    def ids(self) -> list[str]:
        return [row["kb_id"] for row in self.rows]

    def name_for(self, kb_id: str) -> str:
        for row in self.rows:
            if row["kb_id"] == kb_id:
                return row["name"]
        return ""


class DocumentListModel(QAbstractListModel):
    IdRole = Qt.UserRole + 1
    FilenameRole = Qt.UserRole + 2
    StatusRole = Qt.UserRole + 3
    ChunkCountRole = Qt.UserRole + 4
    ByteSizeRole = Qt.UserRole + 5
    ErrorRole = Qt.UserRole + 6

    def __init__(self):
        super().__init__()
        self.rows: list[Document] = []

    def roleNames(self):
        return {
            self.IdRole: b"docId",
            self.FilenameRole: b"filename",
            self.StatusRole: b"status",
            self.ChunkCountRole: b"chunkCount",
            self.ByteSizeRole: b"byteSize",
            self.ErrorRole: b"error",
        }

    def rowCount(self, parent=None):
        parent = parent or QModelIndex()
        return 0 if parent.isValid() else len(self.rows)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.rows):
            return None
        document = self.rows[index.row()]
        if role == self.IdRole:
            return document.id
        if role == self.FilenameRole:
            return document.filename
        if role == self.StatusRole:
            return document.status.value
        if role == self.ChunkCountRole:
            return document.chunk_count
        if role == self.ByteSizeRole:
            return document.byte_size
        if role == self.ErrorRole:
            return document.error or ""
        if role == Qt.DisplayRole:
            return document.filename
        return None

    def refresh(self, documents: list[Document]) -> None:
        self.beginResetModel()
        self.rows = list(documents)
        self.endResetModel()


class KnowledgeService(QObject):
    knowledgeBasesChanged = Signal()
    documentsChanged = Signal()
    indexingChanged = Signal()
    embeddingModelsChanged = Signal()
    retrievalTestFinished = Signal(str)
    errorOccurred = Signal(str)
    knowledgeBaseCreated = Signal(str)

    def __init__(
        self,
        repository: KnowledgeRepository,
        session_repository,
        embedding_factory: EmbeddingFactory,
        data_dir: str | Path,
        *,
        model_lister: ModelLister | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.repository = repository
        self.session_repository = session_repository
        self.embedding_factory = embedding_factory
        self.model_lister = model_lister
        self.data_dir = Path(data_dir)
        self.indexer = None
        self.retriever_factory = None
        self._knowledge_bases = KnowledgeBaseListModel()
        self._documents = DocumentListModel()
        self._current_kb_id = ""
        self._indexing = False
        self._indexing_status = ""
        self._embedding_models: list[dict] = []
        self._embedding_models_loading = False
        self._embedding_models_error = ""
        self._tasks: set[asyncio.Task] = set()
        self._retrievers: dict[str, RetrievalManager] = {}

    @Property(QObject, constant=True)
    def knowledgeBases(self):
        return self._knowledge_bases

    @Property(QObject, constant=True)
    def documents(self):
        return self._documents

    @Property(str, notify=knowledgeBasesChanged)
    def currentKnowledgeBaseId(self):
        return self._current_kb_id

    @Property(bool, notify=indexingChanged)
    def indexing(self):
        return self._indexing

    @Property(str, notify=indexingChanged)
    def indexingStatus(self):
        return self._indexing_status

    @Property("QVariantList", notify=embeddingModelsChanged)
    def embeddingModelOptions(self):
        return list(self._embedding_models)

    @Property(bool, notify=embeddingModelsChanged)
    def embeddingModelsLoading(self):
        return self._embedding_models_loading

    @Property(str, notify=embeddingModelsChanged)
    def embeddingModelsError(self):
        return self._embedding_models_error

    async def start(self) -> None:
        await self.repository.open()
        self.indexer = DocumentIndexer(
            self.repository, _UnavailableEmbedding(), self.data_dir / "knowledge"
        )
        await self.refresh_knowledge_bases()
        if self._knowledge_bases.ids():
            await self.select_knowledge_base(self._knowledge_bases.ids()[0])

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()
        await self.repository.close()

    @Slot(str)
    def loadEmbeddingModels(self, provider_id: str) -> None:
        self._spawn(self._load_embedding_models(provider_id))

    async def _load_embedding_models(self, provider_id: str) -> None:
        self._embedding_models_loading = True
        self._embedding_models_error = ""
        self.embeddingModelsChanged.emit()
        provider_type = ""
        config = self.session_repository.get_provider_config(provider_id)
        if config is not None:
            provider_type = config.config.get("provider_type", config.provider_id)
        discovered: list[str] = []
        if self.model_lister is not None:
            try:
                discovered = await self.model_lister(provider_id)
            except Exception as error:  # noqa: BLE001 - discovery failure must not block manual entry
                self._embedding_models_error = f"无法获取模型列表：{error}"
        self._embedding_models = _embedding_options(provider_type, discovered)
        if not self._embedding_models:
            self._embedding_models_error = (
                self._embedding_models_error
                or "没有从该服务商发现嵌入模型，请换一个服务商，或勾选「手动输入」。"
            )
        self._embedding_models_loading = False
        self.embeddingModelsChanged.emit()

    @Slot()
    def shutdown(self) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        task = loop.create_task(self.stop())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def refresh_knowledge_bases(self) -> None:
        rows = []
        for kb in await self.repository.list_knowledge_bases():
            documents = await self.repository.list_documents(kb.id)
            rows.append(
                {
                    "kb_id": kb.id,
                    "name": kb.name,
                    "description": kb.description,
                    "document_count": len(documents),
                    "chunk_count": sum(document.chunk_count for document in documents),
                    "embedding_model": kb.embedding_model,
                    "chunk_size": kb.chunk_size,
                    "chunk_overlap": kb.chunk_overlap,
                    "top_m_final": kb.top_m_final,
                }
            )
        self._knowledge_bases.refresh(rows)
        self.knowledgeBasesChanged.emit()

    async def select_knowledge_base(self, kb_id: str) -> None:
        self._current_kb_id = kb_id
        await self.refresh_documents(kb_id)
        self.knowledgeBasesChanged.emit()

    async def update_knowledge_base_settings(
        self,
        kb_id: str,
        chunk_size: int,
        chunk_overlap: int,
        top_m_final: int,
    ) -> None:
        if not 128 <= chunk_size <= 2048:
            raise KnowledgeError("分块大小需要在 128 到 2048 之间")
        if not 0 <= chunk_overlap < chunk_size:
            raise KnowledgeError("重复段大小需要小于分块大小")
        if not 1 <= top_m_final <= 20:
            raise KnowledgeError("返回条数需要在 1 到 20 之间")
        await self.repository.update_knowledge_base(
            kb_id,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            top_m_final=top_m_final,
        )
        await self.refresh_knowledge_bases()

    @Slot(str, result="QVariantMap")
    def knowledgeBaseSettings(self, kb_id: str):
        for row in self._knowledge_bases.rows:
            if row["kb_id"] == kb_id:
                return {
                    "chunkSize": row.get("chunk_size", 512),
                    "chunkOverlap": row.get("chunk_overlap", 50),
                    "topMFinal": row.get("top_m_final", 5),
                }
        return {}

    @Slot(str, int, int, int)
    def updateKnowledgeBaseSettings(
        self, kb_id: str, chunk_size: int, chunk_overlap: int, top_m_final: int
    ) -> None:
        async def run() -> None:
            try:
                await self.update_knowledge_base_settings(
                    kb_id, chunk_size, chunk_overlap, top_m_final
                )
            except (KnowledgeError, OSError, RuntimeError, ValueError) as error:
                self.errorOccurred.emit(str(error))

        self._spawn(run())

    async def refresh_documents(self, kb_id: str) -> None:
        documents = await self.repository.list_documents(kb_id) if kb_id else []
        self._documents.refresh(documents)
        self.documentsChanged.emit()

    async def create_knowledge_base(
        self,
        name: str,
        description: str,
        provider_id: str,
        model_id: str,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        embedding_dim: int = 0,
    ) -> KnowledgeBase:
        embedding = await self.embedding_factory(provider_id, model_id)
        if embedding_dim <= 0:
            embedding_dim = await embedding.probe_dimension()
        kb = await self.repository.create_knowledge_base(
            name=name,
            description=description,
            embedding_provider_id=provider_id,
            embedding_model=model_id,
            embedding_dim=embedding_dim,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        await self.refresh_knowledge_bases()
        await self.select_knowledge_base(kb.id)
        self.knowledgeBaseCreated.emit(kb.id)
        return kb

    async def delete_knowledge_base(self, kb_id: str) -> None:
        await self.repository.delete_knowledge_base(kb_id)
        self._retrievers.pop(kb_id, None)
        if self._current_kb_id == kb_id:
            self._current_kb_id = ""
        await self.refresh_knowledge_bases()
        if self._knowledge_bases.ids():
            await self.select_knowledge_base(self._knowledge_bases.ids()[0])
        else:
            await self.refresh_documents("")

    async def import_files(self, kb_id: str, paths: Sequence[str]) -> list[Document]:
        kb = await self.repository.get_knowledge_base(kb_id)
        if kb is None:
            raise KnowledgeError(f"知识库不存在：{kb_id}")
        embedding = await self.embedding_factory(kb.embedding_provider_id, kb.embedding_model)
        indexer = DocumentIndexer(self.repository, embedding, self.data_dir / "knowledge")
        indexed: list[Document] = []
        for path in paths:
            indexed.append(await indexer.index_file(kb_id, path))
        await self.refresh_knowledge_bases()
        await self.refresh_documents(kb_id)
        return indexed

    async def delete_document(self, kb_id: str, doc_id: str) -> None:
        indexer = DocumentIndexer(
            self.repository, _UnavailableEmbedding(), self.data_dir / "knowledge"
        )
        await indexer.delete_document(doc_id)
        await self.refresh_knowledge_bases()
        await self.refresh_documents(kb_id)

    async def available_embedding_choices(self) -> list[dict]:
        choices = []
        for config in self.session_repository.list_provider_configs():
            models = config.config.get("models") or []
            provider_type = config.config.get("provider_type", config.provider_id)
            model_settings = config.config.get("model_settings") or {}
            for model_id in models:
                settings = model_settings.get(model_id) or {}
                if isinstance(settings, dict) and settings.get("enabled") is False:
                    continue
                choices.append(
                    {
                        "providerId": config.provider_id,
                        "providerName": config.display_name or provider_type,
                        "modelId": model_id,
                        "label": f"{config.display_name or provider_type} / {model_id}",
                    }
                )
        return choices

    async def knowledge_base_choices(self) -> list[dict]:
        return [
            {"id": row["kb_id"], "name": row["name"], "embeddingModel": row["embedding_model"]}
            for row in self._knowledge_bases.rows
        ]

    async def retrieve(self, kb_ids: Sequence[str], query: str) -> RetrievalResult:
        results: list[RetrievalResult] = []
        for kb_id in kb_ids:
            kb = await self.repository.get_knowledge_base(kb_id)
            if kb is None:
                continue
            retriever = self._retrievers.get(kb_id)
            if retriever is None:
                embedding = await self.embedding_factory(
                    kb.embedding_provider_id, kb.embedding_model
                )
                retriever = RetrievalManager(self.repository, embedding)
                self._retrievers[kb_id] = retriever
            results.append(await retriever.retrieve([kb_id], query))
        return _merge_results(query, results)

    def kb_ids_for_session(self, session_id: str) -> list[str]:
        return self.session_repository.get_session_knowledge_bases(session_id)

    @Slot(result="QVariantList")
    def knowledgeBaseChoices(self):
        return [
            {"id": row["kb_id"], "name": row["name"], "embeddingModel": row["embedding_model"]}
            for row in self._knowledge_bases.rows
        ]

    @Slot(result="QVariantList")
    def embeddingChoices(self):
        choices: list[dict] = []
        for config in self.session_repository.list_provider_configs():
            models = config.config.get("models") or []
            provider_type = config.config.get("provider_type", config.provider_id)
            model_settings = config.config.get("model_settings") or {}
            for model_id in models:
                settings = model_settings.get(model_id) or {}
                if isinstance(settings, dict) and settings.get("enabled") is False:
                    continue
                choices.append(
                    {
                        "providerId": config.provider_id,
                        "providerName": config.display_name or provider_type,
                        "modelId": model_id,
                        "label": f"{config.display_name or provider_type} / {model_id}",
                    }
                )
        return choices

    @Slot(result="QVariantList")
    def embeddingProviders(self):
        providers: list[dict] = []
        for config in self.session_repository.list_provider_configs():
            provider_type = config.config.get("provider_type", config.provider_id)
            providers.append(
                {
                    "providerId": config.provider_id,
                    "displayName": config.display_name or provider_type,
                    "providerType": provider_type,
                }
            )
        return providers

    @Slot(str)
    def selectKnowledgeBase(self, kb_id: str) -> None:
        self._spawn(self.select_knowledge_base(kb_id))

    @Slot(str, str, str, str, int)
    def createKnowledgeBase(
        self, name: str, description: str, provider_id: str, model_id: str, chunk_size: int
    ) -> None:
        async def run() -> None:
            self._set_indexing(True, "正在创建知识库…")
            try:
                await self.create_knowledge_base(
                    name, description, provider_id, model_id, max(128, min(2048, chunk_size))
                )
            except EmbeddingError as error:
                self.errorOccurred.emit(_embedding_error_message(str(error)))
            except (KnowledgeError, OSError, RuntimeError, ValueError) as error:
                self.errorOccurred.emit(str(error))
            finally:
                self._set_indexing(False, "")

        self._spawn(run())

    @Slot(str)
    def deleteKnowledgeBase(self, kb_id: str) -> None:
        async def run() -> None:
            try:
                await self.delete_knowledge_base(kb_id)
            except (KnowledgeError, OSError) as error:
                self.errorOccurred.emit(str(error))

        self._spawn(run())

    @Slot(str)
    def importDocuments(self, kb_id: str) -> None:
        paths, _ = QFileDialog.getOpenFileNames(None, "选择要导入的文档", "", IMPORT_FILTER)
        if not paths:
            return
        self._spawn(self._import_paths(kb_id, paths))

    async def _import_paths(self, kb_id: str, paths: Sequence[str]) -> None:
        self._set_indexing(True, f"正在索引 {len(paths)} 个文档…")
        progress: ProgressCallback = lambda done, total: self._set_indexing(
            True, f"正在索引：{done}/{total} 分块"
        )
        try:
            kb = await self.repository.get_knowledge_base(kb_id)
            if kb is None:
                raise KnowledgeError(f"知识库不存在：{kb_id}")
            embedding = await self.embedding_factory(
                kb.embedding_provider_id, kb.embedding_model
            )
            indexer = DocumentIndexer(self.repository, embedding, self.data_dir / "knowledge")
            for path in paths:
                try:
                    await indexer.index_file(kb_id, path, progress=progress)
                except (KnowledgeError, OSError, RuntimeError, ValueError) as error:
                    self.errorOccurred.emit(f"{Path(path).name}: {error}")
        finally:
            await self.refresh_knowledge_bases()
            await self.refresh_documents(kb_id)
            self._set_indexing(False, "")

    @Slot(str, str)
    def deleteDocument(self, kb_id: str, doc_id: str) -> None:
        async def run() -> None:
            try:
                await self.delete_document(kb_id, doc_id)
            except (KnowledgeError, OSError) as error:
                self.errorOccurred.emit(str(error))

        self._spawn(run())

    @Slot(str, str)
    def testRetrieval(self, kb_id: str, query: str) -> None:
        async def run() -> None:
            try:
                result = await self.retrieve([kb_id], query)
                self.retrievalTestFinished.emit(json.dumps(result.as_payload(), ensure_ascii=False))
            except (RetrievalError, KnowledgeError, EmbeddingError, OSError, RuntimeError) as error:
                self.retrievalTestFinished.emit(
                    json.dumps({"error": str(error), "hits": []}, ensure_ascii=False)
                )

        self._spawn(run())

    @Slot(str, "QVariantList")
    def setSessionKnowledgeBases(self, session_id: str, kb_ids) -> None:
        self.session_repository.set_session_knowledge_bases(
            session_id, [str(kb_id) for kb_id in kb_ids]
        )

    @Slot(str, result="QVariantList")
    def sessionKnowledgeBases(self, session_id: str):
        return self.session_repository.get_session_knowledge_bases(session_id)

    def _set_indexing(self, value: bool, status: str) -> None:
        self._indexing = value
        self._indexing_status = status
        self.indexingChanged.emit()

    def _spawn(self, coroutine) -> None:
        task = asyncio.ensure_future(coroutine)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)


class _UnavailableEmbedding:
    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        raise EmbeddingError("当前知识库未配置可用的嵌入模型")


def _embedding_error_message(message: str) -> str:
    lowered = message.lower()
    if "404" in message or "400" in message or "not found" in lowered:
        return (
            "该模型不支持嵌入接口（/embeddings 返回错误）。请在「嵌入模型」中填写支持嵌入的模型，"
            "例如 BAAI/bge-m3、text-embedding-3-small 或 nomic-embed-text。"
        )
    return f"嵌入服务调用失败：{message}"


def _merge_results(query: str, results: Sequence[RetrievalResult]) -> RetrievalResult:
    if not results:
        return RetrievalResult(query=query, hits=(), elapsed_ms=0)
    if len(results) == 1:
        return results[0]
    hits = []
    for result in results:
        hits.extend(result.hits)
    hits.sort(key=lambda hit: hit.score, reverse=True)
    limit = max(len(result.hits) for result in results)
    return RetrievalResult(
        query=query,
        hits=tuple(hits[:limit]),
        elapsed_ms=sum(result.elapsed_ms for result in results),
        total_candidates=sum(result.total_candidates for result in results),
        truncated=any(result.truncated for result in results),
    )
