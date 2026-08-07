import asyncio
import os
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path

from PySide6.QtCore import Property, QAbstractListModel, QModelIndex, QObject, Qt, Signal, Slot

from desktop_agent.domain.models import ProviderConfig, SessionStatus
from desktop_agent.providers.openai_compatible import ModelDiscoveryError, OpenAICompatibleClient
from desktop_agent.providers.presets import PRESETS_BY_ID, PROVIDER_PRESETS


def default_system_prompt() -> str:
    return (
        files("desktop_agent.resources")
        .joinpath("default_system_prompt.md")
        .read_text(encoding="utf-8")
        .strip()
    )


class SettingsService(QObject):
    systemPromptChanged = Signal()
    settingsChanged = Signal()

    def __init__(self, repository, data_dir: Path | None = None):
        super().__init__()
        self.repository = repository
        self.data_dir = data_dir

    def get(self, key: str, default=None):
        setting = self.repository.get_app_setting(key)
        return default if setting is None else setting.value

    @Property(str, notify=systemPromptChanged)
    def systemPrompt(self):
        return self.get("system_prompt", default_system_prompt())

    @Property(str, notify=settingsChanged)
    def theme(self):
        return self.get("theme", "system")

    @Property(str, notify=settingsChanged)
    def shellMode(self):
        return self.get("shell_mode", "auto")

    @Property(bool, notify=settingsChanged)
    def startAtLogin(self):
        return bool(self.get("start_at_login", False))

    @Property(str, notify=settingsChanged)
    def logDirectory(self):
        fallback = str(self.data_dir / "logs") if self.data_dir is not None else ""
        return self.get("log_directory", fallback)

    @Slot(str)
    def saveSystemPrompt(self, value: str) -> None:
        self.repository.set_app_setting("system_prompt", value)
        self.systemPromptChanged.emit()

    @Slot()
    def resetSystemPrompt(self) -> None:
        self.repository.set_app_setting("system_prompt", default_system_prompt())
        self.systemPromptChanged.emit()

    @Slot(str, object)
    def setValue(self, key: str, value) -> None:
        self.repository.set_app_setting(key, value)
        self.settingsChanged.emit()


class ModelService(QObject):
    configuredModelsChanged = Signal()
    modelsDiscovered = Signal(str, list)
    discoveryFailed = Signal(str, str)

    def __init__(self, repository, credentials):
        super().__init__()
        self.repository = repository
        self.credentials = credentials
        self._tasks: set[asyncio.Task] = set()

    @Property(list, constant=True)
    def providerPresets(self):
        return [
            {
                "id": preset.id,
                "displayName": preset.display_name,
                "baseUrl": preset.base_url,
                "modelHints": list(preset.model_hints),
            }
            for preset in PROVIDER_PRESETS
        ]

    @Property(list, notify=configuredModelsChanged)
    def configuredModels(self):
        choices = []
        for config in self.repository.list_provider_configs():
            for model_id in config.config.get("models", []):
                choices.append(
                    {
                        "display": f"{model_id} · {config.display_name}",
                        "value": f"{config.provider_id}:{model_id}",
                    }
                )
        return choices or [{"display": "请先配置模型", "value": ""}]

    @Slot(str, str, str, str)
    def saveProvider(self, provider_id: str, base_url: str, api_key: str, model_id: str) -> None:
        preset = PRESETS_BY_ID[provider_id]
        existing = self.repository.get_provider_config(provider_id)
        now = datetime.now(UTC)
        models = [] if not model_id.strip() else [model_id.strip()]
        self.repository.set_provider_config(
            ProviderConfig(
                provider_id=provider_id,
                display_name=preset.display_name,
                base_url=base_url.strip() or preset.base_url,
                config={"models": models, "credential_ref": provider_id},
                created_at=existing.created_at if existing else now,
                updated_at=now,
            )
        )
        if api_key:
            self.credentials.set(provider_id, api_key)
        self.configuredModelsChanged.emit()

    @Slot(str, str, str)
    def discoverModels(self, provider_id: str, base_url: str, api_key: str) -> None:
        task = asyncio.create_task(self._discover(provider_id, base_url, api_key))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _discover(self, provider_id: str, base_url: str, api_key: str) -> None:
        preset = PRESETS_BY_ID[provider_id]
        secret = api_key or self.credentials.get(provider_id)
        client = OpenAICompatibleClient(base_url.strip() or preset.base_url, secret)
        try:
            models = await client.discover_models()
            self.modelsDiscovered.emit(provider_id, models)
        except ModelDiscoveryError as error:
            self.discoveryFailed.emit(provider_id, str(error))
        finally:
            await client.close()


class ArchivedSessionModel(QAbstractListModel):
    IdRole = Qt.UserRole + 1
    TitleRole = Qt.UserRole + 2

    def __init__(self, repository):
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
        self.sessions = self.repository.list_sessions(SessionStatus.ARCHIVED)
        self.endResetModel()


class ArchiveService(QObject):
    changed = Signal()

    def __init__(self, repository, workspaces, active_sessions):
        super().__init__()
        self.repository = repository
        self.workspaces = workspaces
        self.active_sessions = active_sessions
        self.archived = ArchivedSessionModel(repository)

    @Property(QObject, constant=True)
    def archivedSessions(self):
        return self.archived

    @Slot(str)
    def restore(self, session_id: str) -> None:
        self.repository.restore_session(session_id)
        self.archived.refresh()
        self.active_sessions.refresh()
        self.changed.emit()

    @Slot(str)
    def deletePermanently(self, session_id: str) -> None:
        self.workspaces.delete_archived_workspace(session_id)
        self.repository.delete_session(session_id)
        self.archived.refresh()
        self.changed.emit()


class DataService(QObject):
    def __init__(self, data_dir: Path, workspaces_dir: Path):
        super().__init__()
        self.data_dir = data_dir
        self.workspaces_dir = workspaces_dir

    @Property(str, constant=True)
    def dataPath(self):
        return str(self.data_dir)

    @Property(str, constant=True)
    def workspacesPath(self):
        return str(self.workspaces_dir)

    @Slot()
    def openDataDirectory(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(self.data_dir)

    @Slot()
    def openWorkspacesDirectory(self) -> None:
        self.workspaces_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(self.workspaces_dir)
