import asyncio
from contextlib import suppress
from pathlib import Path

from PySide6.QtCore import Property, QAbstractListModel, QModelIndex, QObject, Qt, Signal, Slot

from desktop_agent.agent.loop import AgentLoop
from desktop_agent.agent.prompt import PromptComposer
from desktop_agent.domain.models import MessageRole, MessageStatus
from desktop_agent.providers.openai_compatible import OpenAICompatibleClient
from desktop_agent.security.permissions import SessionAccess
from desktop_agent.tools.files import FileTools
from desktop_agent.tools.powershell import PowerShellExecutor, ShellUnavailable
from desktop_agent.tools.registry import file_tool_registry, powershell_tool


class MessageListModel(QAbstractListModel):
    RoleRole = Qt.UserRole + 1
    ContentRole = Qt.UserRole + 2
    StatusRole = Qt.UserRole + 3
    DetailsRole = Qt.UserRole + 4

    def __init__(self, repository):
        super().__init__()
        self.repository = repository
        self.session_id = ""
        self.messages = []
        self.details = {}

    def roleNames(self):
        return {
            self.RoleRole: b"role",
            self.ContentRole: b"content",
            self.StatusRole: b"status",
            self.DetailsRole: b"details",
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
            content = message.content
            if message.role is MessageRole.ASSISTANT and message.status is MessageStatus.STOPPED:
                content = f"{content}\n\n响应已停止" if content else "响应已停止"
            return content
        if role == self.StatusRole:
            return message.status.value
        if role == self.DetailsRole:
            return self.details.get(message.id, "")
        return None

    def load(self, session_id: str) -> None:
        self.beginResetModel()
        self.session_id = session_id
        self.messages = self.repository.list_messages(session_id) if session_id else []
        self.details = {}
        if session_id:
            runs = iter(self.repository.list_tool_runs(session_id))
            for message in self.messages:
                if message.role is MessageRole.TOOL:
                    run = next(runs, None)
                    if run is not None:
                        self.details[message.id] = run.raw_output
        self.endResetModel()


class ChatService(QObject):
    runningChanged = Signal()
    permissionRequested = Signal(str, str)

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
        self.messages = MessageListModel(repository)
        self._running = False
        self._stop_event: asyncio.Event | None = None
        self._task: asyncio.Task | None = None
        self._permission_future: asyncio.Future | None = None
        self._shell: PowerShellExecutor | None = None
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
        session = self.repository.get_session(self.sessions.currentSessionId)
        if session is None or not session.current_model_id:
            return
        self._running = True
        self.runningChanged.emit()
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._run(session, content.strip()))
        self._task.add_done_callback(self._finished)

    @Slot()
    def stop(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()
        if self._permission_future is not None and not self._permission_future.done():
            self._permission_future.set_result(False)
        if self._shell is not None:
            self._shell.stop()

    @Slot(bool)
    def resolvePermission(self, allowed: bool) -> None:
        if self._permission_future is not None and not self._permission_future.done():
            self._permission_future.set_result(allowed)

    async def _run(self, session, content: str) -> None:
        provider_id, model_id = session.current_model_id.split(":", 1)
        config = self.repository.get_provider_config(provider_id)
        if config is None:
            return
        provider = self.provider_factory(config.base_url, self.credentials.get(provider_id))
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
            async for _ in loop.send_message(
                session.id,
                content,
                model_id=model_id,
                thinking_strength=session.thinking_strength,
                access=access,
                stop_event=self._stop_event,
            ):
                if self.sessions.currentSessionId == session.id:
                    self.messages.load(session.id)
        finally:
            if shell is not None:
                shell.close()
            self._shell = None
            await provider.close()

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
        self._permission_future = asyncio.get_running_loop().create_future()
        self.permissionRequested.emit(request.capability, str(request.path))
        try:
            return bool(await self._permission_future)
        finally:
            self._permission_future = None

    def _finished(self, task) -> None:
        with suppress(asyncio.CancelledError):
            task.exception()
        self._running = False
        self._stop_event = None
        self._task = None
        self.messages.load(self.sessions.currentSessionId)
        self.runningChanged.emit()
