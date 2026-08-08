from pathlib import Path

import pytest
from PySide6.QtCore import QObject, Qt, QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression
from PySide6.QtQuick import QQuickView
from PySide6.QtTest import QTest

from desktop_agent.chat_service import MessageListModel
from desktop_agent.domain.models import MessageRole, MessageStatus
from desktop_agent.storage.database import Database
from desktop_agent.storage.repositories import Repository

COMPONENTS = (
    Path(__file__).parents[2] / "src" / "desktop_agent" / "ui" / "components"
)


def create_component(engine, name):
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(COMPONENTS / name)))
    instance = component.create()
    assert instance is not None, [error.toString() for error in component.errors()]
    return component, instance


@pytest.mark.parametrize(
    ("status", "label", "icon"),
    [
        ("completed", "成功", "✓"),
        ("failed", "失败", "×"),
        ("cancelled", "已取消", "■"),
    ],
)
def test_tool_summary_has_text_and_icon_status(qapp, status, label, icon):
    engine = QQmlEngine()
    _component, summary = create_component(engine, "ToolRunSummary.qml")
    summary.setProperty("toolStatus", status)
    assert summary.property("statusText") == label
    assert summary.property("statusIcon") == icon
    summary.deleteLater()
    engine.deleteLater()


def test_tool_summary_expands_to_ordered_scrollable_details(qapp):
    engine = QQmlEngine()
    _component, summary = create_component(engine, "ToolRunSummary.qml")
    summary.setProperty("width", 360)
    summary.setProperty("toolName", "run_powershell")
    summary.setProperty("toolInput", '{"command":"Get-Date"}')
    summary.setProperty("details", "output\n" * 100)
    collapsed = summary.property("implicitHeight")
    summary.setProperty("expanded", True)
    summary.setProperty("height", summary.property("implicitHeight"))
    qapp.processEvents()

    input_scroll = summary.findChild(QObject, "toolInputScroll")
    output_scroll = summary.findChild(QObject, "toolOutputScroll")
    input_section = summary.findChild(QObject, "toolInputSection")
    output_section = summary.findChild(QObject, "toolOutputSection")
    input_text = summary.findChild(QObject, "toolInputText")
    output_text = summary.findChild(QObject, "toolOutputText")
    assert summary.property("implicitHeight") > collapsed
    assert input_scroll is not None and output_scroll is not None
    assert input_text.property("text") == '{"command":"Get-Date"}'
    assert output_text.property("text").startswith("output\n")
    sections = input_section.parent().children()
    assert sections.index(input_section) < sections.index(output_section)
    assert output_scroll.property("height") == pytest.approx(156)
    summary.deleteLater()
    engine.deleteLater()


def test_collapsed_tool_summary_clips_multiline_output(qapp):
    engine = QQmlEngine()
    _component, summary = create_component(engine, "ToolRunSummary.qml")
    summary.setProperty("width", 600)
    summary.setProperty("summary", "first line\nsecond line\nthird line")
    summary.setProperty("height", summary.property("implicitHeight"))
    qapp.processEvents()

    summary_text = summary.findChild(QObject, "toolSummaryText")
    summary_button = summary.findChild(QObject, "toolSummaryButton")
    assert summary.property("implicitHeight") == 60
    assert summary_text.property("height") <= summary_button.property("height")
    summary.deleteLater()
    engine.deleteLater()


def test_chat_timeline_exposes_tail_follow_controls_and_keyboard(qapp):
    view = QQuickView()
    view.setResizeMode(QQuickView.SizeRootObjectToView)
    view.setSource(QUrl.fromLocalFile(str(COMPONENTS / "ChatView.qml")))
    view.resize(480, 320)
    view.show()
    chat = view.rootObject()
    assert chat is not None, [error.toString() for error in view.errors()]
    timeline = chat.findChild(QObject, "messageTimeline")
    new_content = chat.findChild(QObject, "newContentButton")

    assert timeline is not None
    assert new_content is not None
    assert chat.property("followingTail") is True
    chat.setProperty("followingTail", False)
    chat.setProperty("pendingNewContent", True)
    assert chat.property("newContentAvailable") is True

    timeline.forceActiveFocus()
    QTest.keyClick(view, Qt.Key_End, Qt.ControlModifier)
    qapp.processEvents()
    assert chat.property("followingTail") is True
    assert chat.property("pendingNewContent") is False
    view.close()
    view.deleteLater()


def test_pending_assistant_shows_thinking_until_first_token(qapp, tmp_path):
    database = Database(tmp_path / "agent.sqlite3")
    repository = Repository(database)
    session = repository.create_session("Draft", str(tmp_path / "workspace"))
    repository.append_message(session.id, MessageRole.USER, "hello")
    draft = repository.append_message(
        session.id,
        MessageRole.ASSISTANT,
        "",
        status=MessageStatus.STOPPED,
        completion_marker=False,
    )
    model = MessageListModel(repository)
    model.load(session.id)

    view = QQuickView()
    view.setResizeMode(QQuickView.SizeRootObjectToView)
    view.setInitialProperties({"model": model, "running": True})
    view.setSource(QUrl.fromLocalFile(str(COMPONENTS / "ChatView.qml")))
    view.resize(480, 320)
    view.show()
    chat = view.rootObject()
    qapp.processEvents()

    context = QQmlEngine.contextForObject(chat)
    delegate, is_undefined = QQmlExpression(
        context, chat, "messageAt(1)"
    ).evaluate()
    assert is_undefined is False
    indicator = delegate.findChild(QObject, "thinkingIndicator")
    assert indicator is not None
    assert indicator.property("visible") is True

    model.update_message_content(draft.id, "首个 token")
    qapp.processEvents()
    assert indicator.property("visible") is False

    view.close()
    view.deleteLater()
    database.close()


def test_scrollbar_size_and_position_mapping_stay_stable(qapp, tmp_path):
    database = Database(tmp_path / "agent.sqlite3")
    repository = Repository(database)
    session = repository.create_session("Draft", str(tmp_path / "workspace"))
    for index in range(40):
        content = f"消息 {index} " + "不同高度的内容 " * (4 + index % 8 * 5)
        repository.append_message(session.id, MessageRole.USER, content)
    model = MessageListModel(repository)
    model.load(session.id)

    view = QQuickView()
    view.setResizeMode(QQuickView.SizeRootObjectToView)
    view.setInitialProperties({"model": model})
    view.setSource(QUrl.fromLocalFile(str(COMPONENTS / "ChatView.qml")))
    view.resize(640, 360)
    view.show()
    qapp.processEvents()
    QTest.qWait(30)

    chat = view.rootObject()
    timeline = chat.findChild(QObject, "messageTimeline")
    scrollbar = chat.findChild(QObject, "messageScrollBar")
    content_height = timeline.property("contentHeight")
    viewport_height = timeline.property("height")
    scroll_range = content_height - viewport_height
    thumb_size = scrollbar.property("size")

    assert scroll_range > 0
    assert 0 < thumb_size < 1
    assert timeline.property("contentY") == pytest.approx(scroll_range, abs=1)

    for fraction in (0.25, 0.5, 1.0):
        timeline.setProperty("contentY", scroll_range * fraction)
        qapp.processEvents()
        assert timeline.property("contentHeight") == pytest.approx(content_height)
        assert scrollbar.property("size") == pytest.approx(thumb_size)
        normalized_position = scrollbar.property("position") / (1 - thumb_size)
        assert normalized_position == pytest.approx(fraction, abs=0.01)

    view.close()
    view.deleteLater()
    database.close()
