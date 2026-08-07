from pathlib import Path

import pytest

from desktop_agent.storage.database import Database
from desktop_agent.storage.repositories import InvalidSessionState, Repository
from desktop_agent.workspaces.service import WorkspaceService


class FakeRecycleBin:
    def __init__(self):
        self.deleted: list[Path] = []

    def delete(self, path: Path) -> None:
        self.deleted.append(path)


@pytest.fixture
def service(tmp_path):
    database = Database(tmp_path / "agent.sqlite3")
    repo = Repository(database)
    fake = FakeRecycleBin()
    value = WorkspaceService(tmp_path / "workspaces", repo, fake)
    yield value, repo, fake
    database.close()


def test_create_workspace_uses_session_id(service):
    workspace, _, _ = service
    path = workspace.create_for_session("session-1")
    assert path == workspace.root_dir / "session-1"
    assert path.is_dir()


def test_repository_and_workspace_can_share_the_same_session_id(service):
    workspace, repo, _ = service
    path = workspace.create_for_session("session-1")
    session = repo.create_session("Draft", str(path), session_id="session-1")
    assert session.id == "session-1"
    assert Path(session.workspace_path).name == session.id


def test_associate_external_directory_is_normalized(service, tmp_path):
    workspace, repo, _ = service
    path = workspace.create_for_session("session-1")
    session = repo.create_session("Draft", str(path))
    external = tmp_path / "project"
    external.mkdir()
    associated = workspace.associate_external_directory(session.id, external / ".." / "project")
    assert associated == external.resolve()
    assert repo.get_session(session.id).associated_directory == str(external.resolve())


def test_delete_archived_workspace_calls_recycle_bin_adapter(service):
    workspace, repo, fake = service
    path = workspace.create_for_session("session-1")
    session = repo.create_session("Draft", str(path))
    repo.archive_session(session.id)
    workspace.delete_archived_workspace(session.id)
    assert fake.deleted == [path]


def test_delete_active_workspace_is_rejected(service):
    workspace, repo, _ = service
    path = workspace.create_for_session("session-1")
    session = repo.create_session("Draft", str(path))
    with pytest.raises(InvalidSessionState):
        workspace.delete_archived_workspace(session.id)


def test_delete_never_uses_associated_external_directory(service, tmp_path):
    workspace, repo, fake = service
    session = repo.create_session("Draft", str(workspace.create_for_session("session-1")))
    external = tmp_path / "project"
    external.mkdir()
    workspace.associate_external_directory(session.id, external)
    repo.archive_session(session.id)
    workspace.delete_archived_workspace(session.id)
    assert external not in fake.deleted


def test_local_paths_uses_platformdirs(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "desktop_agent.settings.user_data_dir", lambda app_name: str(tmp_path / app_name)
    )
    from desktop_agent.settings import local_paths

    paths = local_paths("TestAgent")
    assert paths.data_dir == tmp_path / "TestAgent"
    assert paths.database == paths.data_dir / "agent.sqlite3"
    assert paths.workspaces == paths.data_dir / "workspaces"
