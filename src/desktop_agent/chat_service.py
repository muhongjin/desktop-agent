import asyncio
import json
import re
from contextlib import suppress
from dataclasses import replace
from pathlib import Path

from keyring.errors import KeyringError
from PySide6.QtCore import Property, QAbstractListModel, QModelIndex, QObject, Qt, Signal, Slot

from desktop_agent.agent.loop import AgentLoop
from desktop_agent.agent.prompt import PromptComposer
from desktop_agent.domain.models import MessageRole, MessageStatus
from desktop_agent.providers.openai_compatible import (
    AssistantTurn,
    OpenAICompatibleClient,
    ProviderError,
    TextDelta,
)
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
        self.beginResetModel()
        self.session_id = session_id
        self.messages = self.repository.list_messages(session_id) if session_id else []
        self.details = {}
        self.tool_runs = {}
        if session_id:
            runs = iter(self.repository.list_tool_runs(session_id))
            for message in self.messages:
                if message.role is MessageRole.TOOL:
                    run = next(runs, None)
                    if run is not None:
                        self.details[message.id] = run.raw_output
                        self.tool_runs[message.id] = run
        self.endResetModel()

    def update_message_content(self, message_id: str, content: str) -> None:
        for row, message in enumerate(self.messages):
            if message.id != message_id:
                continue
            self.messages[row] = replace(message, content=content)
            index = self.index(row, 0)
            self.dataChanged.emit(index, index, [self.ContentRole])
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
    permissionRequested = Signal(str, str, str)
    sessionTitleChanged = Signal(str)

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
    ):
        super().__init__()
        self.repository = repository
        self.sessions = sessions
        self.models = models
        self.settings = settings
        self.permission_broker = permission_broker
        self.credentials = credentials
        self.safe_mode = safe_mode
        self.provider_factory = provider_factory or OpenAICompatibleClient
        self.title_provider_factory = title_provider_factory or self.provider_factory
        self.messages = MessageListModel(repository)
        self._running = False
        self._stop_event: asyncio.Event | None = None
        self._task: asyncio.Task | None = None
        self._title_tasks: set[asyncio.Task] = set()
        self._permission_future: asyncio.Future | None = None
        self._shell: PowerShellExecutor | None = None
        self._active_session_id = ""
        self._session_permissions: dict[str, set[str]] = {}
        self.sessions.currentSessionChanged.connect(self.reload)
        self.reload()

    @Property(QObject, constant=True)
    def messageModel(self):
        return self.messages

    @Property(bool, notify=runningChanged)
    def running(self):
        return self._running

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
        self._start_title_generation(session, content)
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
        self._running = True
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

    @Slot()
    def shutdown(self) -> None:
        self.stop()
        for task in self._title_tasks:
            task.cancel()

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
    ) -> None:
        await asyncio.sleep(0)
        try:
            api_key = await asyncio.to_thread(self.credentials.get, provider_id)
            provider = self.provider_factory(config.base_url, api_key)
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
        access = self._access(session)
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
        )
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
                        self.messages.append_messages(event.data["messages"])
                    elif event.type == "text_delta":
                        self.messages.update_message_content(
                            event.data["message_id"], event.data.get("content", "")
                        )
                    elif event.type == "tool_finished":
                        self.messages.load(session.id)
        finally:
            if shell is not None:
                shell.close()
            self._shell = None
            self._active_session_id = ""
            await provider.close()

    def _start_title_generation(self, session, content: str) -> None:
        if (
            session.title != "新对话"
            or not session.current_model_id
            or self.repository.session_has_messages(session.id)
        ):
            return
        task = asyncio.create_task(self._generate_title(session, content))
        self._title_tasks.add(task)
        task.add_done_callback(self._title_finished)

    async def _generate_title(self, session, content: str) -> None:
        provider_id, model_id = session.current_model_id.split(":", 1)
        config = self.repository.get_provider_config(provider_id)
        generated = ""
        provider = None
        if config is not None:
            try:
                api_key = await asyncio.to_thread(self.credentials.get, provider_id)
                provider = self.title_provider_factory(config.base_url, api_key)
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
                if provider is not None:
                    with suppress(Exception):
                        await provider.close()
        title = self._clean_title(generated, content)
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

    def _access(self, session):
        associated = session.associated_directory
        workspace = Path(session.workspace_path)
        associated_path = Path(associated) if associated else None
        if self.sessions.fullAccess:
            return SessionAccess.full_access(workspace, associated_path)
        if session.execution_mode == "none":
            return SessionAccess.none(workspace, associated_path)
        return SessionAccess.local(workspace, associated_path)

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
        self._stop_event = None
        self._task = None
        self.messages.load(self.sessions.currentSessionId)
        self.runningChanged.emit()
