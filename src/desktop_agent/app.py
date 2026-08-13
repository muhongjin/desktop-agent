import os
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QCoreApplication,
    QModelIndex,
    QObject,
    Qt,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from desktop_agent.chat_service import ChatService
from desktop_agent.domain.models import SessionStatus
from desktop_agent.security.credentials import KeyringCredentialStore
from desktop_agent.security.permissions import PermissionBroker
from desktop_agent.services import ArchiveService, DataService, ModelService, SettingsService
from desktop_agent.settings import LocalPaths, local_paths
from desktop_agent.storage.database import Database
from desktop_agent.storage.repositories import Repository
from desktop_agent.workspaces.service import WorkspaceService


class SessionListModel(QAbstractListModel):
    IdRole = Qt.UserRole + 1
    TitleRole = Qt.UserRole + 2

    def __init__(self, repository: Repository):
        super().__init__()
        self.repository = repository
        self.sessions = []
        self.refresh()

    def roleNames(self):
        return {self.IdRole: b"sessionId", self.TitleRole: b"title"}

    def rowCount(self, parent=None):
        parent = parent or QModelIndex()
        return 0 if parent.isValid() else len(self.sessions)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.sessions):
            return None
        session = self.sessions[index.row()]
        if role == self.IdRole:
            return session.id
        if role in {self.TitleRole, Qt.DisplayRole}:
            return session.title
        return None

    def refresh(self) -> None:
        self.beginResetModel()
        self.sessions = self.repository.list_sessions(SessionStatus.ACTIVE)
        self.endResetModel()


class SessionService(QObject):
    currentSessionChanged = Signal()
    sessionArchived = Signal(str)

    def __init__(
        self, repository: Repository, workspaces: WorkspaceService, settings: SettingsService
    ):
        super().__init__()
        self.repository = repository
        self.workspaces = workspaces
        self.settings = settings
        self.sessions = SessionListModel(repository)
        self._current_session_id = self.sessions.sessions[0].id if self.sessions.sessions else ""
        self._full_access: set[str] = set()

    @Property(QObject, constant=True)
    def activeSessions(self):
        return self.sessions

    @Property(str, notify=currentSessionChanged)
    def currentSessionId(self):
        return self._current_session_id

    @Property(bool, notify=currentSessionChanged)
    def hasCurrentSession(self):
        return bool(self._current_session_id)

    @Property(str, notify=currentSessionChanged)
    def currentSessionTitle(self):
        session = self._current_session()
        return session.title if session else ""

    @Property(str, notify=currentSessionChanged)
    def currentModelId(self):
        session = self._current_session()
        return session.current_model_id if session and session.current_model_id else ""

    @Property(str, notify=currentSessionChanged)
    def thinkingStrength(self):
        session = self._current_session()
        return session.thinking_strength if session and session.thinking_strength else "medium"

    @Property(str, notify=currentSessionChanged)
    def executionMode(self):
        session = self._current_session()
        return session.execution_mode if session else "local"

    @Property(bool, notify=currentSessionChanged)
    def fullAccess(self):
        return self._current_session_id in self._full_access

    @Slot(str)
    def selectSession(self, session_id: str) -> None:
        if session_id != self._current_session_id:
            self._current_session_id = session_id
            self.currentSessionChanged.emit()

    @Slot(str)
    def refreshSessionTitle(self, session_id: str) -> None:
        self.sessions.refresh()
        if session_id == self._current_session_id:
            self.currentSessionChanged.emit()

    @Slot(result=str)
    def createSession(self) -> str:
        session_id = str(uuid4())
        workspace = self.workspaces.create_for_session(session_id)
        session = self.repository.create_session(
            "新对话",
            str(workspace),
            current_model_id=self.settings.get("recent_model_id"),
            thinking_strength=self.settings.get("recent_thinking_strength", "medium"),
            execution_mode="local",
            session_id=session_id,
        )
        self.sessions.refresh()
        self._current_session_id = session.id
        self.currentSessionChanged.emit()
        return session.id

    @Slot(str)
    def archiveSession(self, session_id: str) -> None:
        if not session_id or self.repository.get_session(session_id) is None:
            return
        was_current = session_id == self._current_session_id
        self._full_access.discard(session_id)
        self.repository.archive_session(session_id)
        self.sessionArchived.emit(session_id)
        self.sessions.refresh()
        if was_current:
            self._current_session_id = (
                self.sessions.sessions[0].id if self.sessions.sessions else ""
            )
            self.currentSessionChanged.emit()

    @Slot(str)
    def openWorkspace(self, session_id: str) -> None:
        session = self.repository.get_session(session_id)
        if session is None:
            return
        Path(session.workspace_path).mkdir(parents=True, exist_ok=True)
        os.startfile(session.workspace_path)

    @Slot(str, str)
    def renameSession(self, session_id: str, title: str) -> None:
        if self.repository.get_session(session_id) is None or not title.strip():
            return
        self.repository.set_unique_session_title(session_id, title)
        self.refreshSessionTitle(session_id)

    @Slot(str)
    def setCurrentModel(self, model_id: str) -> None:
        if not self._current_session_id:
            return
        self.repository.update_session_preferences(self._current_session_id, model_id=model_id)
        self.settings.setValue("recent_model_id", model_id)
        self.currentSessionChanged.emit()

    @Slot(str)
    def setThinkingStrength(self, value: str) -> None:
        if not self._current_session_id:
            return
        self.repository.update_session_preferences(
            self._current_session_id, thinking_strength=value
        )
        self.settings.setValue("recent_thinking_strength", value)
        self.currentSessionChanged.emit()

    @Slot(str)
    def setExecutionMode(self, value: str) -> None:
        if not self._current_session_id:
            return
        self.repository.update_session_preferences(self._current_session_id, execution_mode=value)
        self.settings.setValue("recent_execution_mode", value)
        self.currentSessionChanged.emit()

    @Slot(bool)
    def setFullAccess(self, enabled: bool) -> None:
        if not self._current_session_id:
            return
        if enabled:
            self._full_access.add(self._current_session_id)
        else:
            self._full_access.discard(self._current_session_id)
        self.currentSessionChanged.emit()

    def _current_session(self):
        if not self._current_session_id:
            return None
        return self.repository.get_session(self._current_session_id)


class ApplicationServices(QObject):
    def __init__(
        self,
        paths: LocalPaths,
        repository: Repository,
        workspaces: WorkspaceService,
        safe_mode=False,
    ):
        super().__init__()
        self.paths = paths
        self.repository = repository
        self.workspaces = workspaces
        self.credentials = KeyringCredentialStore()
        self.permissions = PermissionBroker()
        self.settings = SettingsService(repository, paths.data_dir)
        self.models = ModelService(repository, self.credentials)
        self.sessions = SessionService(repository, workspaces, self.settings)
        self.archive = ArchiveService(repository, workspaces, self.sessions.sessions)
        self.data = DataService(paths.data_dir, paths.workspaces)
        self.chat = ChatService(
            repository,
            self.sessions,
            self.models,
            self.settings,
            self.permissions,
            self.credentials,
            safe_mode,
        )
        self.chat.sessionTitleChanged.connect(self.sessions.refreshSessionTitle)
        self.sessions.sessionArchived.connect(self.archive.archived.refresh)
        self.sessions.sessionArchived.connect(self.chat.stopSession)
        self.sessions.sessionArchived.connect(self.chat.clearSessionPermissions)
        self.sessions.currentSessionChanged.connect(self._warm_current_model)
        self.models.providerConfigsChanged.connect(self._warm_current_model)
        self._warm_current_model()

    def _warm_current_model(self) -> None:
        self.models.warmModel(self.sessions.currentModelId)


async def build_application(
    *,
    paths: LocalPaths | None = None,
    repository: Repository | None = None,
    safe_mode: bool = False,
) -> QQmlApplicationEngine:
    resolved_paths = paths or local_paths()
    icon = QIcon(str(Path(__file__).parent / "resources" / "app-icon.ico"))
    database = repository.database if repository is not None else Database(resolved_paths.database)
    resolved_repository = repository or Repository(database)
    workspaces = WorkspaceService(resolved_paths.workspaces, resolved_repository)
    services = ApplicationServices(resolved_paths, resolved_repository, workspaces, safe_mode)
    application = QCoreApplication.instance()
    if application is not None:
        application.aboutToQuit.connect(services.chat.shutdown)
    engine = QQmlApplicationEngine()
    services.setParent(engine)
    services.sessions.setParent(services)
    services.sessions.sessions.setParent(services.sessions)
    services.settings.setParent(services)
    services.models.setParent(services)
    services.archive.setParent(services)
    services.archive.archived.setParent(services.archive)
    services.data.setParent(services)
    services.chat.setParent(services)
    services.chat.messages.setParent(services.chat)
    engine._services = services
    engine._database = database
    engine.destroyed.connect(database.close)
    engine.rootContext().setContextProperty("sessionService", services.sessions)
    engine.rootContext().setContextProperty("modelService", services.models)
    engine.rootContext().setContextProperty("settingsService", services.settings)
    engine.rootContext().setContextProperty("archiveService", services.archive)
    engine.rootContext().setContextProperty("dataService", services.data)
    engine.rootContext().setContextProperty("chatService", services.chat)
    QQuickStyle.setStyle("Basic")
    qml_path = Path(__file__).parent / "ui" / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml_path)))
    if not engine.rootObjects():
        database.close()
        raise RuntimeError(f"Unable to load QML application: {qml_path}")
    window = engine.rootObjects()[0]
    window.setIcon(icon)
    window.show()
    current_model = services.sessions.currentModelId
    current_provider = ""
    if ":" in current_model:
        config_id = current_model.split(":", 1)[0]
        config = resolved_repository.get_provider_config(config_id)
        if config is not None:
            current_provider = config.config.get("provider_type", config.provider_id)
    services.models.startMetadataRefresh(current_provider)
    return engine
