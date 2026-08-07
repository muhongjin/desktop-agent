from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_dir

APP_NAME = "DesktopAgent"


@dataclass(frozen=True, slots=True)
class LocalPaths:
    data_dir: Path
    database: Path
    workspaces: Path


def local_paths(app_name: str = APP_NAME) -> LocalPaths:
    data_dir = Path(user_data_dir(app_name))
    return LocalPaths(
        data_dir=data_dir, database=data_dir / "agent.sqlite3", workspaces=data_dir / "workspaces"
    )
