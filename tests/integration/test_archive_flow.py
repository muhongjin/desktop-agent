from pathlib import Path

import pytest

from desktop_agent.services import (
    ArchiveService,
    ModelService,
    SettingsService,
    default_system_prompt,
)
from desktop_agent.storage.database import Database
from desktop_agent.storage.repositories import InvalidSessionState, Repository
from desktop_agent.workspaces.service import WorkspaceService


class MemoryCredentials:
    def __init__(self):
        self.values = {}

    def get(self, provider_id):
        return self.values.get(provider_id)

    def set(self, provider_id, secret):
        self.values[provider_id] = secret


class RecycleBin:
    def __init__(self):
        self.deleted: list[Path] = []

    def delete(self, path):
        self.deleted.append(path)


class ActiveSessions:
    def __init__(self):
        self.refresh_count = 0

    def refresh(self):
        self.refresh_count += 1


@pytest.fixture
def context(tmp_path):
    database = Database(tmp_path / "agent.sqlite3")
    repo = Repository(database)
    recycle = RecycleBin()
    workspaces = WorkspaceService(tmp_path / "workspaces", repo, recycle)
    active = ActiveSessions()
    archive = ArchiveService(repo, workspaces, active)
    yield repo, workspaces, recycle, archive
    database.close()


def test_archived_chat_can_be_restored(context):
    repo, workspaces, _, archive = context
    path = workspaces.create_for_session("session-1")
    session = repo.create_session("Draft", str(path))
    repo.archive_session(session.id)
    archive.archived.refresh()
    archive.restore(session.id)
    assert repo.get_session(session.id).status.value == "active"


def test_delete_moves_only_automatic_workspace_then_removes_record(context):
    repo, workspaces, recycle, archive = context
    path = workspaces.create_for_session("session-1")
    external = path.parent.parent / "external"
    external.mkdir()
    session = repo.create_session("Draft", str(path))
    workspaces.associate_external_directory(session.id, external)
    repo.archive_session(session.id)
    archive.deletePermanently(session.id)
    assert recycle.deleted == [path]
    assert external.exists()
    assert repo.get_session(session.id) is None


def test_active_chat_cannot_be_deleted(context):
    repo, workspaces, _, archive = context
    path = workspaces.create_for_session("session-1")
    session = repo.create_session("Draft", str(path))
    with pytest.raises(InvalidSessionState):
        archive.deletePermanently(session.id)


def test_model_config_never_exposes_api_key(tmp_path):
    database = Database(tmp_path / "agent.sqlite3")
    repo = Repository(database)
    credentials = MemoryCredentials()
    service = ModelService(repo, credentials)
    service.saveProvider("openai", "https://example.test/v1", "top-secret", "model-a")
    assert "top-secret" not in str(service.configuredModels)
    assert "top-secret" not in str(repo.get_provider_config("openai"))
    assert credentials.values["openai"] == "top-secret"
    database.close()


def test_system_prompt_reset_restores_packaged_default(tmp_path):
    database = Database(tmp_path / "agent.sqlite3")
    service = SettingsService(Repository(database))
    service.saveSystemPrompt("custom")
    service.resetSystemPrompt()
    assert service.systemPrompt == default_system_prompt()
    database.close()
