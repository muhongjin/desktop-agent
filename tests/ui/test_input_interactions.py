import pytest
from PySide6.QtCore import QMetaObject, QObject, QPointF, Qt
from PySide6.QtQml import QQmlEngine, QQmlExpression
from PySide6.QtTest import QSignalSpy, QTest

from desktop_agent.app import build_application
from desktop_agent.settings import LocalPaths


@pytest.mark.asyncio
async def test_main_window_exposes_keyboard_and_focus_contract(qapp, tmp_path):
    paths = LocalPaths(tmp_path, tmp_path / "agent.sqlite3", tmp_path / "workspaces")
    engine = await build_application(paths=paths)
    root = engine.rootObjects()[0]
    composer = root.findChild(QObject, "composerBar")
    editor = root.findChild(QObject, "messageInput")

    assert root.findChild(QObject, "newSessionShortcut") is not None
    assert root.findChild(QObject, "stopShortcut") is not None
    assert composer.metaObject().indexOfMethod("focusEditor()") >= 0
    assert composer.metaObject().indexOfMethod("submit()") >= 0
    assert composer.property("hasModel") is False
    assert root.findChild(QObject, "sendButton").property("visible") is False
    assert root.findChild(QObject, "configureModelsButton").property("visible") is True

    root.requestActivate()
    qapp.processEvents()
    QTest.keyClick(root, Qt.Key_N, Qt.ControlModifier)
    qapp.processEvents()
    assert engine._services.sessions.hasCurrentSession is True
    assert editor.property("activeFocus") is True

    sent = QSignalSpy(composer.sendRequested)
    composer.setProperty("selectedModel", "openai:test-model")
    editor.setProperty("text", "first line")
    QTest.keyClick(root, Qt.Key_Return)
    qapp.processEvents()
    assert sent.count() == 0
    assert "\n" in editor.property("text")

    editor.setProperty("text", "send this")
    QTest.keyClick(root, Qt.Key_Return, Qt.ControlModifier)
    qapp.processEvents()
    assert sent.count() == 1
    assert sent.at(0) == ["send this"]
    assert editor.property("text") == ""

    root.close()
    engine.deleteLater()


@pytest.mark.asyncio
async def test_permission_and_session_navigation_controls_are_keyboard_reachable(
    qapp, tmp_path
):
    paths = LocalPaths(tmp_path, tmp_path / "agent.sqlite3", tmp_path / "workspaces")
    engine = await build_application(paths=paths)
    root = engine.rootObjects()[0]
    session_list = root.findChild(QObject, "sessionList")
    permission_dialog = root.findChild(QObject, "permissionDialog")
    reject_button = root.findChild(QObject, "permissionRejectButton")

    assert session_list.metaObject().indexOfMethod("moveCursor(QVariant)") >= 0
    assert session_list.metaObject().indexOfMethod("activateCursor()") >= 0
    assert permission_dialog is not None
    assert root.findChild(QObject, "permissionCapability") is not None
    assert root.findChild(QObject, "permissionTarget") is not None
    assert reject_button is not None
    assert root.findChild(QObject, "permissionAllowButton") is not None
    assert root.findChild(QObject, "permissionAllowSessionButton") is not None
    assert root.findChild(QObject, "permissionOperationDetail") is not None
    assert root.findChild(QObject, "fullAccessOffButton") is not None

    rejected = QSignalSpy(permission_dialog.resolved)
    permission_dialog.setProperty("capability", "fs.write")
    permission_dialog.setProperty("targetPath", "C:/outside/result.txt")
    QMetaObject.invokeMethod(permission_dialog, "open")
    qapp.processEvents()
    assert reject_button.property("activeFocus") is True

    QTest.keyClick(root, Qt.Key_Escape)
    qapp.processEvents()
    assert rejected.count() == 1
    assert rejected.at(0) == ["deny"]
    assert permission_dialog.property("opened") is False

    root.close()
    engine.deleteLater()


@pytest.mark.asyncio
async def test_session_context_menu_opens_on_right_click(qapp, tmp_path):
    paths = LocalPaths(tmp_path, tmp_path / "agent.sqlite3", tmp_path / "workspaces")
    engine = await build_application(paths=paths)
    root = engine.rootObjects()[0]
    session_id = engine._services.sessions.createSession()
    session_list = root.findChild(QObject, "sessionList")
    qapp.processEvents()

    context = QQmlEngine.contextForObject(session_list)
    delegate, is_undefined = QQmlExpression(
        context, session_list, "itemAtIndex(0)"
    ).evaluate()
    assert is_undefined is False
    position = delegate.mapToScene(
        QPointF(delegate.width() / 2, delegate.height() / 2)
    ).toPoint()

    QTest.mouseClick(root, Qt.RightButton, Qt.NoModifier, position)
    qapp.processEvents()

    menu = root.findChild(QObject, "sessionContextMenu")
    assert menu.property("opened") is True
    assert session_list.property("contextSessionId") == session_id

    QTest.keyClick(root, Qt.Key_Escape)
    root.close()
    engine.deleteLater()
