from pathlib import Path

import pytest
from PySide6.QtCore import QObject, QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine

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


def test_tool_run_summary_expands(qapp):
    engine = QQmlEngine()
    path = (
        Path(__file__).parents[2]
        / "src"
        / "desktop_agent"
        / "ui"
        / "components"
        / "ToolRunSummary.qml"
    )
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(path)))
    summary = component.create()
    assert summary is not None, [error.toString() for error in component.errors()]
    summary.setProperty("summary", "wrote result.txt")
    summary.setProperty("details", "full tool output")
    collapsed = summary.property("implicitHeight")
    summary.setProperty("expanded", True)
    qapp.processEvents()
    assert summary.property("implicitHeight") > collapsed
    summary.deleteLater()
    engine.deleteLater()
