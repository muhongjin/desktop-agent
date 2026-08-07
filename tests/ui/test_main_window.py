import pytest
from PySide6.QtCore import QObject

from desktop_agent.app import build_application
from desktop_agent.settings import LocalPaths


@pytest.mark.asyncio
async def test_main_window_exposes_confirmed_controls(qapp, tmp_path):
    paths = LocalPaths(tmp_path, tmp_path / "agent.sqlite3", tmp_path / "workspaces")
    engine = await build_application(paths=paths)
    root = engine.rootObjects()[0]
    expected = {
        "sessionList",
        "chatView",
        "composerBar",
        "modelSelector",
        "thinkingSelector",
        "executionModeSelector",
        "fullAccessToggle",
        "sendButton",
        "stopButton",
        "openWorkspaceButton",
    }
    found = {name for name in expected if root.findChild(QObject, name) is not None}
    assert found == expected
    root.close()
    engine.deleteLater()
