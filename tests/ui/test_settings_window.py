import pytest
from PySide6.QtCore import QObject, Qt
from PySide6.QtTest import QTest

from desktop_agent.app import build_application
from desktop_agent.settings import LocalPaths


async def build_settings_window(tmp_path):
    paths = LocalPaths(tmp_path, tmp_path / "agent.sqlite3", tmp_path / "workspaces")
    engine = await build_application(paths=paths)
    root = engine.rootObjects()[0]
    settings = root.findChild(QObject, "settingsWindow")
    return engine, root, settings


@pytest.mark.asyncio
async def test_settings_window_has_exactly_five_pages_and_required_states(qapp, tmp_path):
    engine, root, settings = await build_settings_window(tmp_path)
    pages = settings.findChild(QObject, "settingsPages")

    assert settings is not None
    assert settings.property("minimumWidth") >= 780
    assert settings.property("minimumHeight") >= 540
    assert pages.property("count") == 5
    assert settings.findChild(QObject, "manualModelInput") is not None
    assert settings.findChild(QObject, "apiKeyInput") is not None
    assert settings.findChild(QObject, "modelDiscoveryStatus") is not None
    assert settings.findChild(QObject, "archivedChatsEmptyState") is not None
    for page_name in (
        "modelServicePage",
        "systemPromptPage",
        "archivedChatsPage",
        "dataWorkspacePage",
        "appSettingsPage",
    ):
        assert settings.findChild(QObject, page_name) is not None

    root.close()
    engine.deleteLater()


@pytest.mark.asyncio
async def test_settings_navigation_supports_home_and_end(qapp, tmp_path):
    engine, root, settings = await build_settings_window(tmp_path)
    navigation = settings.findChild(QObject, "settingsNavigation")
    settings.show()
    qapp.processEvents()

    QTest.keyClick(settings, Qt.Key_End)
    qapp.processEvents()
    assert navigation.property("currentIndex") == 4

    QTest.keyClick(settings, Qt.Key_Home)
    qapp.processEvents()
    assert navigation.property("currentIndex") == 0

    settings.close()
    root.close()
    engine.deleteLater()
