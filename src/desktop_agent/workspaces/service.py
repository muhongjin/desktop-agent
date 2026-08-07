import os
from pathlib import Path
from typing import Protocol

from send2trash import send2trash

from desktop_agent.domain.models import SessionStatus
from desktop_agent.storage.repositories import InvalidSessionState


class RecycleBinAdapter(Protocol):
    def delete(self, path: Path) -> None: ...


class Send2TrashAdapter:
    def delete(self, path: Path) -> None:
        send2trash(str(path))


class WorkspaceService:
    def __init__(self, root_dir: str | Path, session_repository, recycle_bin_adapter: RecycleBinAdapter | None = None):
        self.root_dir = Path(root_dir).expanduser().resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.session_repository = session_repository
        self.recycle_bin_adapter = recycle_bin_adapter or Send2TrashAdapter()

    def workspace_path(self, session_id: str) -> Path:
        return self.root_dir / session_id

    def create_for_session(self, session_id: str) -> Path:
        path = self.workspace_path(session_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def associate_external_directory(self, session_id: str, path: str | Path) -> Path:
        normalized = Path(path).expanduser().resolve(strict=True)
        if not normalized.is_dir():
            raise NotADirectoryError(normalized)
        session = self.session_repository.get_session(session_id)
        if session is None:
            raise KeyError(f"Unknown session: {session_id}")
        self.session_repository.set_associated_directory(session_id, str(normalized))
        return normalized

    def open_workspace(self, session_id: str) -> None:
        path = self.workspace_path(session_id)
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(str(path))

    def delete_archived_workspace(self, session_id: str) -> None:
        session = self.session_repository.get_session(session_id)
        if session is None:
            raise KeyError(f"Unknown session: {session_id}")
        if session.status is not SessionStatus.ARCHIVED:
            raise InvalidSessionState("Only archived sessions can be deleted")
        automatic = Path(session.workspace_path).expanduser().resolve()
        if not automatic.is_relative_to(self.root_dir):
            raise InvalidSessionState("Automatic workspace is outside the workspace root")
        if automatic.exists():
            self.recycle_bin_adapter.delete(automatic)
