import pytest
from PySide6.QtCore import QObject, Qt
from PySide6.QtQml import QQmlEngine, QQmlExpression
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
    assert settings.findChild(QObject, "providerConfigList") is not None
    assert settings.findChild(QObject, "providerConfigRepeater") is not None
    assert settings.findChild(QObject, "addProviderButton") is not None
    assert settings.findChild(QObject, "providerPresetGrid") is not None
    assert settings.findChild(QObject, "providerTimeoutInput") is not None
    assert settings.findChild(QObject, "apiProtocolSelector") is not None
    assert settings.findChild(QObject, "manualModelInput") is not None
    assert settings.findChild(QObject, "apiKeyInput") is not None
    assert settings.findChild(QObject, "modelDiscoveryStatus") is not None
    assert settings.findChild(QObject, "modelDiscoveryResults") is not None
    assert settings.findChild(QObject, "discoveredModelSearch") is not None
    assert settings.findChild(QObject, "discoveredModelList") is not None
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
async def test_discovered_models_require_explicit_searchable_selection(qapp, tmp_path):
    engine, root, settings = await build_settings_window(tmp_path)
    settings.show()
    qapp.processEvents()
    page = settings.findChild(QObject, "modelServicePage")
    model_input = settings.findChild(QObject, "manualModelInput")
    search = settings.findChild(QObject, "discoveredModelSearch")
    model_list = settings.findChild(QObject, "discoveredModelList")
    results = settings.findChild(QObject, "modelDiscoveryResults")

    page.setProperty("mode", "editor")
    page.setProperty("discovering", True)
    page.setProperty("discoveryRequestId", "discovery-test")
    engine._services.models.modelsDiscovered.emit(
        "discovery-test", ["alpha-model", "beta-model", "gamma-model"]
    )
    qapp.processEvents()

    assert model_input.property("text") == ""
    assert page.property("selectedModels").toVariant() == []
    assert results.property("visible") is True
    assert model_list.property("count") == 3
    assert "第一个" not in page.property("statusMessage")

    search.setProperty("text", "beta")
    qapp.processEvents()
    assert model_list.property("count") == 1

    context = QQmlEngine.contextForObject(model_list)
    delegate, is_undefined = QQmlExpression(
        context, model_list, "itemAtIndex(0)"
    ).evaluate()
    assert is_undefined is False
    delegate.click()
    qapp.processEvents()

    assert page.property("selectedModels").toVariant() == ["beta-model"]

    settings.close()
    root.close()
    engine.deleteLater()


@pytest.mark.asyncio
async def test_saved_provider_instances_are_listed_as_cards(qapp, tmp_path):
    engine, root, settings = await build_settings_window(tmp_path)
    page = settings.findChild(QObject, "modelServicePage")
    cards = settings.findChild(QObject, "providerConfigRepeater")

    first_id = engine._services.models.saveProviderConfig(
        "", "openai", "工作 OpenAI", "https://one.test/v1", "", 45, "responses", ["model-a"]
    )
    second_id = engine._services.models.saveProviderConfig(
        "", "openai", "备用 OpenAI", "https://two.test/v1", "", 90, "responses", ["model-b"]
    )
    qapp.processEvents()

    assert first_id != second_id
    assert page.property("mode") == "list"
    assert cards.property("count") == 2
    assert settings.findChild(QObject, "providerSelector") is None

    context = QQmlEngine.contextForObject(cards)
    first_card, is_undefined = QQmlExpression(context, cards, "itemAt(0)").evaluate()
    assert is_undefined is False
    card_children = first_card.findChildren(QObject)
    assert all(
        child.property("placeholderText") != "输入自定义模型 ID"
        for child in card_children
    )
    assert all(child.property("text") != "×" for child in card_children)

    settings.close()
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
