import asyncio
import json
import re
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import replace
from inspect import signature
from pathlib import Path

from keyring.errors import KeyringError
from PySide6.QtCore import Property, QAbstractListModel, QModelIndex, QObject, Qt, Signal, Slot

from desktop_agent.agent.loop import AgentLoop, RetrievalOutcome
from desktop_agent.agent.prompt import PromptComposer
from desktop_agent.domain.models import MessageRole, MessageStatus
from desktop_agent.knowledge.retriever import format_retrieval_context
from desktop_agent.providers.openai_compatible import (
    AssistantTurn,
    OpenAICompatibleClient,
    ProviderError,
    TextDelta,
)
from desktop_agent.providers.presets import PRESETS_BY_ID
from desktop_agent.security.permissions import SessionAccess
from desktop_agent.tools.files import FileTools
from desktop_agent.tools.powershell import PowerShellExecutor, ShellUnavailable
from desktop_agent.tools.registry import file_tool_registry, powershell_tool


class MessageListModel(QAbstractListModel):
    RoleRole = Qt.UserRole + 1
    ContentRole = Qt.UserRole + 2
    StatusRole = Qt.UserRole + 3
    DetailsRole = Qt.UserRole + 4
    ToolNameRole = Qt.UserRole + 5
    ToolStatusRole = Qt.UserRole + 6
    ToolInputRole = Qt.UserRole + 7
    CompletionMarkerRole = Qt.UserRole + 8
    RetrievalRole = Qt.UserRole + 9

    def __init__(self, repository):
        super().__init__()
        self.repository = repository
        self.session_id = ""
        self.messages = []
        self.details = {}
        self.tool_runs = {}

    def roleNames(self):
        return {
            self.RoleRole: b"role",
            self.ContentRole: b"content",
            self.StatusRole: b"status",
            self.DetailsRole: b"details",
            self.ToolNameRole: b"toolName",
            self.ToolStatusRole: b"toolStatus",
            self.ToolInputRole: b"toolInput",
            self.CompletionMarkerRole: b"completionMarker",
            self.RetrievalRole: b"retrieval",
        }

    def rowCount(self, parent=None):
        parent = parent or QModelIndex()
        return 0 if parent.isValid() else len(self.messages)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.messages):
            return None
        message = self.messages[index.row()]
        if role == self.RoleRole:
            return message.role.value
        if role in {self.ContentRole, Qt.DisplayRole}:
            return message.content
        if role == self.StatusRole:
            return message.status.value
        if role == self.CompletionMarkerRole:
            return message.completion_marker
        if role == self.RetrievalRole:
            return json.dumps(message.retrieval, ensure_ascii=False) if message.retrieval else ""
        if role == self.DetailsRole:
            return self.details.get(message.id, "")
        tool_run = self.tool_runs.get(message.id)
        if role == self.ToolNameRole:
            return tool_run.tool_name if tool_run is not None else ""
        if role == self.ToolStatusRole:
            return tool_run.status.value if tool_run is not None else ""
        if role == self.ToolInputRole:
            return tool_run.input_json if tool_run is not None else ""
        return None

    def load(self, session_id: str) -> None:
        messages = self.repository.list_messages(session_id) if session_id else []
        details = {}
        tool_runs = {}
        if session_id:
            runs = iter(self.repository.list_tool_runs(session_id))
            for message in messages:
                if message.role is MessageRole.TOOL:
                    run = next(runs, None)
                    if run is not None:
                        details[message.id] = run.raw_output
                        tool_runs[message.id] = run
        if session_id == self.session_id and [item.id for item in messages] == [
            item.id for item in self.messages
        ]:
            previous_details = self.details
            previous_tool_runs = self.tool_runs
            self.details = details
            self.tool_runs = tool_runs
            for row, (previous, current) in enumerate(zip(self.messages, messages)):
                roles = []
                if previous.content != current.content:
                    roles.append(self.ContentRole)
                if previous.status != current.status:
                    roles.append(self.StatusRole)
                if previous.completion_marker != current.completion_marker:
                    roles.append(self.CompletionMarkerRole)
                if previous_details.get(current.id, "") != details.get(current.id, ""):
                    roles.append(self.DetailsRole)
                previous_run = previous_tool_runs.get(current.id)
                current_run = tool_runs.get(current.id)
                if previous_run != current_run:
                    roles.extend(
                        [self.ToolNameRole, self.ToolStatusRole, self.ToolInputRole]
                    )
                self.messages[row] = current
                if roles:
                    index = self.index(row, 0)
                    self.dataChanged.emit(index, index, roles)
            return
        self.beginResetModel()
        self.session_id = session_id
        self.messages = messages
        self.details = details
        self.tool_runs = tool_runs
        self.endResetModel()

    def update_message_content(self, message_id: str, content: str) -> None:
        for row, message in enumerate(self.messages):
            if message.id != message_id:
                continue
            self.messages[row] = replace(message, content=content)
            index = self.index(row, 0)
            self.dataChanged.emit(index, index, [self.ContentRole])
            return

    def set_retrieval(self, message_id: str, payload: dict) -> None:
        for row, message in enumerate(self.messages):
            if message.id != message_id:
                continue
            self.messages[row] = replace(message, retrieval=payload)
            index = self.index(row, 0)
            self.dataChanged.emit(index, index, [self.RetrievalRole])
            return

    def append_messages(self, messages) -> None:
        existing = {message.id for message in self.messages}
        additions = [
            message
            for message in messages
            if message.session_id == self.session_id and message.id not in existing
        ]
        if not additions:
            return
        first = len(self.messages)
        self.beginInsertRows(QModelIndex(), first, first + len(additions) - 1)
        self.messages.extend(additions)
        self.endInsertRows()


class ChatService(QObject):
    runningChanged = Signal()
    retryStatusChanged = Signal()
    permissionRequested = Signal(str, str, str)
    sessionTitleChanged = Signal(str)
    retrievalFailed = Signal(str)

    def __init__(
        self,
        repository,
        sessions,
        models,
        settings,
        permission_broker,
        credentials,
        safe_mode=False,
        provider_factory=None,
        title_provider_factory=None,
        knowledge=None,
    ):
        super().__init__()
        self.repository = repository
        self.sessions = sessions
        self.models = models
        self.settings = settings
        self.permission_broker = permission_broker
        self.credentials = credentials
        self.safe_mode = safe_mode
        self.knowledge = knowledge
        self.provider_factory = provider_factory or OpenAICompatibleClient
        self.title_provider_factory = title_provider_factory or self.provider_factory
        self.messages = MessageListModel(repository)
        self._running = False
        self._retry_status = ""
        self._stop_event: asyncio.Event | None = None
        self._task: asyncio.Task | None = None
        self._title_tasks: set[asyncio.Task] = set()
        self._permission_future: asyncio.Future | None = None
        self._shell: PowerShellExecutor | None = None
        self._active_session_id = ""
        self._running_session_id = ""
        self._session_permissions: dict[str, set[str]] = {}
        self.sessions.currentSessionChanged.connect(self.reload)
        self.reload()

    @staticmethod
    def _provider(factory, config, api_key):
        timeout = config.config.get("timeout", 120)
        provider_type = config.config.get("provider_type", config.provider_id)
        preset = PRESETS_BY_ID.get(provider_type, PRESETS_BY_ID["custom"])
        api_protocol = config.config.get("api_protocol", preset.api_protocol)
        try:
            signature(factory).bind(
                config.base_url,
                api_key,
                timeout=timeout,
                api_protocol=api_protocol,
            )
        except (TypeError, ValueError):
            try:
                signature(factory).bind(config.base_url, api_key, timeout=timeout)
            except (TypeError, ValueError):
                return factory(config.base_url, api_key)
            return factory(config.base_url, api_key, timeout=timeout)
        return factory(
            config.base_url,
            api_key,
            timeout=timeout,
            api_protocol=api_protocol,
        )

    async def _acquire_provider(self, factory, provider_id, config, model_id=None):
        if factory is OpenAICompatibleClient and self.models is not None:
            try:
                provider = await self.models.clientFor(provider_id, config, model_id)
            except TypeError:
                provider = await self.models.clientFor(provider_id, config)
            return provider, False
        api_key = await asyncio.to_thread(self.credentials.get, provider_id)
        return self._provider(factory, config, api_key), True

    @Property(QObject, constant=True)
    def messageModel(self):
        return self.messages

    @Property(bool, notify=runningChanged)
    def running(self):
        return self._running

    @Property(str, notify=retryStatusChanged)
    def retryStatus(self):
        return self._retry_status

    def _set_retry_status(self, value: str) -> None:
        if self._retry_status == value:
            return
        self._retry_status = value
        self.retryStatusChanged.emit()

    @Slot()
    def reload(self) -> None:
        self.messages.load(self.sessions.currentSessionId)

    @Slot(str)
    def sendMessage(self, content: str) -> None:
        if self._running or not content.strip() or not self.sessions.currentSessionId:
            return
        content = content.strip()
        session = self.repository.get_session(self.sessions.currentSessionId)
        if session is None or not session.current_model_id:
            return
        provider_id, model_id = session.current_model_id.split(":", 1)
        config = self.repository.get_provider_config(provider_id)
        if config is None:
            return
        generate_title = (
            session.title == "新对话"
            and bool(session.current_model_id)
            and not self.repository.session_has_messages(session.id)
        )
        user_message = self.repository.append_message(
            session.id,
            MessageRole.USER,
            content,
            model_id=model_id,
            thinking_strength=session.thinking_strength,
        )
        draft = self.repository.append_message(
            session.id,
            MessageRole.ASSISTANT,
            "",
            model_id=model_id,
            thinking_strength=session.thinking_strength,
            status=MessageStatus.STOPPED,
            completion_marker=False,
        )
        self.messages.append_messages((user_message, draft))
        self._set_retry_status("")
        self._running = True
        self._running_session_id = session.id
        self.runningChanged.emit()
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(
            self._run(
                session,
                content,
                provider_id,
                model_id,
                config,
                (user_message, draft),
                generate_title,
            )
        )
        self._task.add_done_callback(self._finished)

    @Slot()
    def stop(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()
        if self._permission_future is not None and not self._permission_future.done():
            self._permission_future.set_result("deny")
        if self._shell is not None:
            self._shell.stop()

    @Slot(str)
    def stopSession(self, session_id: str) -> None:
        if session_id == self._running_session_id:
            self.stop()

    @Slot()
    def shutdown(self) -> None:
        self.stop()
        for task in self._title_tasks:
            task.cancel()
        if self.models is not None:
            self.models.closeClients()

    @Slot(str)
    def resolvePermission(self, decision: str) -> None:
        if self._permission_future is not None and not self._permission_future.done():
            self._permission_future.set_result(decision)

    @Slot(str)
    def clearSessionPermissions(self, session_id: str) -> None:
        self._session_permissions.pop(session_id, None)

    async def _run(
        self,
        session,
        content: str,
        provider_id: str,
        model_id: str,
        config,
        initial_messages,
        generate_title: bool,
    ) -> None:
        await asyncio.sleep(0)
        try:
            provider, provider_owned = await self._acquire_provider(
                self.provider_factory, provider_id, config, model_id
            )
        except (KeyringError, OSError, RuntimeError, TypeError, ValueError) as error:
            draft = initial_messages[1]
            visible_error = f"错误：{error}"
            self.repository.update_message(
                draft.id,
                visible_error,
                MessageStatus.STOPPED,
                completion_marker=True,
            )
            if self.sessions.currentSessionId == session.id:
                self.messages.update_message_content(draft.id, visible_error)
            return
        knowledge_kb_ids = self._session_knowledge_kb_ids(session.id)
        access = self._access(session, knowledge_kb_ids)
        files = FileTools(self.permission_broker, access)
        registry = {} if self.safe_mode else file_tool_registry(files)
        try:
            shell = None if self.safe_mode else PowerShellExecutor(self.settings.shellMode)
            if shell is not None:
                self._shell = shell
                registry["run_powershell"] = powershell_tool(shell, session.workspace_path)
        except ShellUnavailable:
            shell = None
        loop = AgentLoop(
            self.repository,
            PromptComposer(self.settings.systemPrompt),
            provider,
            self.permission_broker,
            registry,
            self._confirm_permission,
            context_limit=self._model_context_limit(config, model_id),
            retrieval_provider=self._build_retrieval_provider(knowledge_kb_ids),
        )
        completed = False
        try:
            self._active_session_id = session.id
            async for event in loop.send_message(
                session.id,
                content,
                model_id=model_id,
                thinking_strength=session.thinking_strength,
                access=access,
                stop_event=self._stop_event,
                initial_messages=initial_messages,
            ):
                if self.sessions.currentSessionId == session.id:
                    if event.type == "turn_started":
                        self._set_retry_status("")
                        self.messages.append_messages(event.data["messages"])
                    elif event.type == "text_delta":
                        self._set_retry_status("")
                        self.messages.update_message_content(
                            event.data["message_id"], event.data.get("content", "")
                        )
                    elif event.type == "retrying":
                        self._set_retry_status(
                            f"正在重新连接 {event.data['attempt']}/"
                            f"{event.data['max_attempts']}"
                        )
                    elif event.type == "retrieval":
                        payload = event.data.get("payload") or {}
                        message_id = event.data.get("message_id")
                        if message_id:
                            self.repository.set_message_retrieval(message_id, payload)
                            self.messages.set_retrieval(message_id, payload)
                    elif event.type == "retrieval_failed":
                        self.retrievalFailed.emit(str(event.data.get("error", "")))
                    elif event.type == "tool_finished":
                        self._set_retry_status("")
                        self.messages.load(session.id)
                    elif event.type in {"tool_started", "turn_finished", "turn_stopped"}:
                        self._set_retry_status("")
            completed = True
        finally:
            if shell is not None:
                shell.close()
            self._shell = None
            self._active_session_id = ""
            if provider_owned:
                await provider.close()
        if completed and generate_title:
            self._start_title_generation(session, content)

    @staticmethod
    def _model_context_limit(config, model_id: str) -> int | None:
        settings = config.config.get("model_settings", {})
        values = settings.get(model_id, {}) if isinstance(settings, dict) else {}
        if not isinstance(values, dict):
            return None
        try:
            context = int(values.get("context", values.get("context_window", 0)) or 0)
        except (TypeError, ValueError):
            return None
        return context if context > 0 else None

    def _start_title_generation(self, session, content: str) -> None:
        if session.title != "新对话" or not session.current_model_id:
            return
        task = asyncio.create_task(self._generate_title(session, content))
        self._title_tasks.add(task)
        task.add_done_callback(self._title_finished)

    async def _generate_title(self, session, content: str) -> None:
        provider_id, model_id = session.current_model_id.split(":", 1)
        config = self.repository.get_provider_config(provider_id)
        generated = ""
        provider = None
        provider_owned = False
        if config is not None:
            try:
                provider, provider_owned = await self._acquire_provider(
                    self.title_provider_factory, provider_id, config, model_id
                )
                parts = []
                async for event in provider.stream_chat(
                    model_id=model_id,
                    messages=(
                        {
                            "role": "system",
                            "content": (
                                "为这段对话生成一个具体、易区分的短标题。使用用户消息的语言，"
                                "不超过20个字符。只输出标题，不要引号、Markdown、换行或解释。"
                            ),
                        },
                        {"role": "user", "content": content},
                    ),
                    tools=(),
                ):
                    if isinstance(event, TextDelta):
                        parts.append(event.text)
                    elif isinstance(event, AssistantTurn) and event.text:
                        generated = event.text
                generated = generated or "".join(parts)
            except asyncio.CancelledError:
                raise
            except (KeyringError, OSError, ProviderError, RuntimeError, TypeError, ValueError):
                generated = ""
            finally:
                if provider is not None and provider_owned:
                    with suppress(Exception):
                        await provider.close()
        title = self._clean_title(generated, content)
        current_session = self.repository.get_session(session.id)
        if current_session is None or current_session.title != "新对话":
            return
        try:
            self.repository.set_unique_session_title(session.id, title)
        except KeyError:
            return
        self.sessionTitleChanged.emit(session.id)

    @staticmethod
    def _clean_title(generated: str, fallback: str) -> str:
        first_line = next((line.strip() for line in generated.splitlines() if line.strip()), "")
        first_line = first_line.strip(" \t\r\n#*`_\"'“”‘’《》")
        title = re.sub(
            r"^(?:会话标题|对话标题|标题|conversation title|title)\s*[:：]\s*",
            "",
            first_line,
            flags=re.IGNORECASE,
        )
        title = re.sub(r"\s+", " ", title).strip(" \t\r\n#*`_\"'“”‘’《》")
        if not title or title == "新对话":
            title = re.sub(r"\s+", " ", fallback).strip()
        return title[:24].rstrip() or "未命名对话"

    def _title_finished(self, task: asyncio.Task) -> None:
        self._title_tasks.discard(task)
        with suppress(asyncio.CancelledError):
            task.exception()

    def _access(self, session, knowledge_kb_ids=()):
        associated = session.associated_directory
        workspace = Path(session.workspace_path)
        associated_path = Path(associated) if associated else None
        kb_ids = frozenset(knowledge_kb_ids)
        if self.sessions.fullAccess:
            return SessionAccess.full_access(workspace, associated_path, kb_ids)
        if session.execution_mode == "none":
            return SessionAccess.none(workspace, associated_path, kb_ids)
        return SessionAccess.local(workspace, associated_path, kb_ids)

    def _session_knowledge_kb_ids(self, session_id: str) -> list[str]:
        if self.safe_mode or self.knowledge is None:
            return []
        try:
            return list(self.knowledge.kb_ids_for_session(session_id))
        except Exception:  # noqa: BLE001 - knowledge lookup must not block chat
            return []

    def _build_retrieval_provider(self, kb_ids: Sequence[str]):
        if not kb_ids or self.knowledge is None:
            return None
        return _KnowledgeRetrievalProvider(self.knowledge, kb_ids)

    async def _confirm_permission(self, request, tool, arguments) -> bool:
        grants = self._session_permissions.get(self._active_session_id, set())
        if request.risk not in self.permission_broker.high_risks and request.capability in grants:
            return True
        self._permission_future = asyncio.get_running_loop().create_future()
        detail = self._permission_detail(tool, arguments)
        self.permissionRequested.emit(request.capability, str(request.path), detail)
        try:
            decision = await self._permission_future
            if decision == "session" and request.risk not in self.permission_broker.high_risks:
                self._session_permissions.setdefault(self._active_session_id, set()).add(
                    request.capability
                )
            return decision in {"once", "session"}
        finally:
            self._permission_future = None

    def _permission_detail(self, tool, arguments) -> str:
        if tool.name == "run_powershell":
            shell = self._shell.shell if self._shell is not None else self.settings.shellMode
            return f"{shell}\n{arguments.get('command', '')}".strip()
        return json.dumps(arguments, ensure_ascii=False, indent=2)

    def _finished(self, task) -> None:
        with suppress(asyncio.CancelledError):
            task.exception()
        self._running = False
        self._set_retry_status("")
        self._stop_event = None
        self._task = None
        self._running_session_id = ""
        self.messages.load(self.sessions.currentSessionId)
        self.runningChanged.emit()


class _KnowledgeRetrievalProvider:
    def __init__(self, knowledge, kb_ids: Sequence[str]):
        self._knowledge = knowledge
        self._kb_ids = list(kb_ids)

    async def retrieve(self, session_id: str, query: str) -> RetrievalOutcome | None:
        result = await self._knowledge.retrieve(self._kb_ids, query)
        if not result.hits:
            return None
        return RetrievalOutcome(
            context=format_retrieval_context(result),
            payload=result.as_payload(),
        )
