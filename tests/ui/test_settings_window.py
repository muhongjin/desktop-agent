import pytest
from PySide6.QtCore import QObject

from desktop_agent.app import build_application
from desktop_agent.settings import LocalPaths


@pytest.mark.asyncio
async def test_settings_window_has_exactly_five_pages_and_manual_model_input(qapp, tmp_path):
    paths = LocalPaths(tmp_path, tmp_path / "agent.sqlite3", tmp_path / "workspaces")
    engine = await build_application(paths=paths)
    root = engine.rootObjects()[0]
    settings = root.findChild(QObject, "settingsWindow")
    pages = settings.findChild(QObject, "settingsPages")
    assert settings is not None
    assert pages.property("count") == 5
    assert settings.findChild(QObject, "manualModelInput") is not None
    assert settings.findChild(QObject, "apiKeyInput") is not None
    root.close()
    engine.deleteLater()
