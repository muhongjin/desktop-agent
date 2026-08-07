import os
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QModelIndex,
    QObject,
    Qt,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from desktop_agent.domain.models import SessionStatus
from desktop_agent.security.credentials import KeyringCredentialStore
from desktop_agent.security.permissions import PermissionBroker
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

    def __init__(self, repository: Repository, workspaces: WorkspaceService):
        super().__init__()
        self.repository = repository
        self.workspaces = workspaces
        self.sessions = SessionListModel(repository)
        self._current_session_id = self.sessions.sessions[0].id if self.sessions.sessions else ""

    @Property(QObject, constant=True)
    def activeSessions(self):
        return self.sessions

    @Property(str, notify=currentSessionChanged)
    def currentSessionId(self):
        return self._current_session_id

    @Property(bool, notify=currentSessionChanged)
    def hasCurrentSession(self):
        return bool(self._current_session_id)

    @Slot(str)
    def selectSession(self, session_id: str) -> None:
        if session_id != self._current_session_id:
            self._current_session_id = session_id
            self.currentSessionChanged.emit()

    @Slot(result=str)
    def createSession(self) -> str:
        workspace_id = str(uuid4())
        workspace = self.workspaces.create_for_session(workspace_id)
        session = self.repository.create_session("新对话", str(workspace))
        self.sessions.refresh()
        self._current_session_id = session.id
        self.currentSessionChanged.emit()
        return session.id

    @Slot()
    def archiveCurrent(self) -> None:
        if not self._current_session_id:
            return
        self.repository.archive_session(self._current_session_id)
        self.sessions.refresh()
        self._current_session_id = self.sessions.sessions[0].id if self.sessions.sessions else ""
        self.currentSessionChanged.emit()

    @Slot()
    def openCurrentWorkspace(self) -> None:
        if not self._current_session_id:
            return
        session = self.repository.get_session(self._current_session_id)
        if session is None:
            return
        Path(session.workspace_path).mkdir(parents=True, exist_ok=True)
        os.startfile(session.workspace_path)


class ApplicationServices(QObject):
    def __init__(self, paths: LocalPaths, repository: Repository, workspaces: WorkspaceService):
        super().__init__()
        self.paths = paths
        self.repository = repository
        self.workspaces = workspaces
        self.credentials = KeyringCredentialStore()
        self.permissions = PermissionBroker()
        self.sessions = SessionService(repository, workspaces)


async def build_application(
    *,
    paths: LocalPaths | None = None,
    repository: Repository | None = None,
) -> QQmlApplicationEngine:
    resolved_paths = paths or local_paths()
    database = repository.database if repository is not None else Database(resolved_paths.database)
    resolved_repository = repository or Repository(database)
    workspaces = WorkspaceService(resolved_paths.workspaces, resolved_repository)
    services = ApplicationServices(resolved_paths, resolved_repository, workspaces)
    engine = QQmlApplicationEngine()
    services.setParent(engine)
    services.sessions.setParent(services)
    services.sessions.sessions.setParent(services.sessions)
    engine._services = services
    engine._database = database
    engine.destroyed.connect(database.close)
    engine.rootContext().setContextProperty("sessionService", services.sessions)
    QQuickStyle.setStyle("Basic")
    qml_path = Path(__file__).parent / "ui" / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml_path)))
    if not engine.rootObjects():
        database.close()
        raise RuntimeError(f"Unable to load QML application: {qml_path}")
    return engine
