from pathlib import Path

import pytest
from PySide6.QtCore import QObject, QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine

from desktop_agent.app import build_application
from desktop_agent.domain.models import SessionStatus
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
        "sessionContextMenu",
        "renameSessionMenuItem",
        "openWorkspaceMenuItem",
        "archiveSessionMenuItem",
        "renameSessionDialog",
        "renameSessionInput",
    }
    found = {name for name in expected if root.findChild(QObject, name) is not None}
    assert found == expected
    assert root.findChild(QObject, "openWorkspaceButton") is None
    assert root.findChild(QObject, "archiveButton") is None
    assert root.property("title") == "Desktop Agent"
    assert engine._services.sessions.currentSessionTitle == ""
    root.close()
    engine.deleteLater()


@pytest.mark.asyncio
async def test_session_context_actions_target_the_requested_chat(
    qapp, tmp_path, monkeypatch
):
    paths = LocalPaths(tmp_path, tmp_path / "agent.sqlite3", tmp_path / "workspaces")
    engine = await build_application(paths=paths)
    sessions = engine._services.sessions
    repository = engine._services.repository
    first_id = sessions.createSession()
    second_id = sessions.createSession()

    sessions.renameSession(first_id, "项目计划")
    sessions.renameSession(second_id, "项目计划")

    assert repository.get_session(first_id).title == "项目计划"
    assert repository.get_session(second_id).title == "项目计划（2）"
    assert sessions.currentSessionId == second_id

    sessions.archiveSession(first_id)
    assert repository.get_session(first_id).status is SessionStatus.ARCHIVED
    assert sessions.currentSessionId == second_id

    opened = []
    monkeypatch.setattr("desktop_agent.app.os.startfile", opened.append)
    sessions.openWorkspace(second_id)
    assert opened == [repository.get_session(second_id).workspace_path]

    engine.rootObjects()[0].close()
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
