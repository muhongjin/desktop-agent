from pathlib import Path

import pytest
from PySide6.QtCore import QObject, QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression

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
        "executionModePicker",
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
    assert root.findChild(QObject, "fullAccessToggle") is None
    assert root.findChild(QObject, "fullAccessOffButton") is None
    assert root.property("title") == "Desktop Agent"
    assert engine._services.sessions.currentSessionTitle == ""
    root.close()
    engine.deleteLater()


@pytest.mark.asyncio
async def test_execution_mode_picker_combines_all_and_new_chats_default_local(qapp, tmp_path):
    paths = LocalPaths(tmp_path, tmp_path / "agent.sqlite3", tmp_path / "workspaces")
    engine = await build_application(paths=paths)
    root = engine.rootObjects()[0]
    sessions = engine._services.sessions
    engine._services.settings.setValue("recent_execution_mode", "none")
    first_id = sessions.createSession()
    qapp.processEvents()

    picker = root.findChild(QObject, "executionModePicker")
    selector = root.findChild(QObject, "executionModeSelector")
    popup = root.findChild(QObject, "executionModePopup")
    choices = root.findChild(QObject, "executionModeChoiceList")
    context = QQmlEngine.contextForObject(picker)

    assert sessions.executionMode == "local"
    assert sessions.fullAccess is False
    assert picker.property("mode") == "local"
    assert choices.property("count") == 3

    QQmlExpression(context, picker, "choose(2)").evaluate()
    qapp.processEvents()
    assert sessions.executionMode == "local"
    assert sessions.fullAccess is True
    assert picker.property("mode") == "all"

    QQmlExpression(context, picker, "choose(0)").evaluate()
    qapp.processEvents()
    assert sessions.executionMode == "none"
    assert sessions.fullAccess is False
    assert picker.property("mode") == "none"

    selector_context = QQmlEngine.contextForObject(selector)
    QQmlExpression(selector_context, selector, "click()").evaluate()
    qapp.processEvents()
    assert popup.property("opened") is True
    assert popup.property("y") < 0

    second_id = sessions.createSession()
    qapp.processEvents()
    assert second_id != first_id
    assert sessions.executionMode == "local"
    assert sessions.fullAccess is False
    assert picker.property("mode") == "local"

    root.close()
    engine.deleteLater()


@pytest.mark.asyncio
async def test_model_preference_picker_expands_right_and_keeps_session_signals(qapp, tmp_path):
    paths = LocalPaths(tmp_path, tmp_path / "agent.sqlite3", tmp_path / "workspaces")
    engine = await build_application(paths=paths)
    root = engine.rootObjects()[0]
    models = engine._services.models
    sessions = engine._services.sessions
    config_id = models.saveProviderConfig(
        "",
        "openai",
        "OpenAI",
        "https://example.test/v1",
        "",
        120,
        "responses",
        ["gpt-5.6-luna", "gpt-5.6-sol"],
    )
    sessions.createSession()
    sessions.setCurrentModel(f"{config_id}:gpt-5.6-sol")
    sessions.setThinkingStrength("high")
    qapp.processEvents()

    picker = root.findChild(QObject, "modelPreferencePicker")
    selector = root.findChild(QObject, "modelSelector")
    popup = root.findChild(QObject, "modelPreferencePopup")
    main_panel = root.findChild(QObject, "modelPreferenceMainPanel")
    model_menu = root.findChild(QObject, "modelMenuButton")

    assert picker.property("summaryText") == "gpt-5.6-sol  高"
    assert "OpenAI" not in picker.property("summaryText")

    context = QQmlEngine.contextForObject(selector)
    QQmlExpression(context, selector, "click()").evaluate()
    qapp.processEvents()
    assert popup.property("opened") is True

    context = QQmlEngine.contextForObject(model_menu)
    QQmlExpression(context, model_menu, "click()").evaluate()
    qapp.processEvents()
    detail_panel = root.findChild(QObject, "modelPreferenceDetailPanel")
    model_list = root.findChild(QObject, "modelChoiceList")
    assert model_list is not None
    assert popup.property("width") > main_panel.property("width")
    assert detail_panel.property("x") >= main_panel.property("width")

    context = QQmlEngine.contextForObject(picker)
    QQmlExpression(context, picker, "chooseModel(0)").evaluate()
    qapp.processEvents()
    assert sessions.currentModelId == f"{config_id}:gpt-5.6-luna"

    QQmlExpression(context, picker, "chooseThinking(0)").evaluate()
    qapp.processEvents()
    assert sessions.thinkingStrength == "low"

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
