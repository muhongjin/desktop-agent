import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from desktop_agent.domain.models import ProviderConfig
from desktop_agent.services import (
    ArchiveService,
    ModelService,
    SettingsService,
    default_system_prompt,
)
from desktop_agent.storage.database import Database
from desktop_agent.storage.repositories import InvalidSessionState, Repository
from desktop_agent.workspaces.service import WorkspaceService


class MemoryCredentials:
    def __init__(self):
        self.values = {}

    def get(self, provider_id):
        return self.values.get(provider_id)

    def set(self, provider_id, secret):
        self.values[provider_id] = secret


class RecycleBin:
    def __init__(self):
        self.deleted: list[Path] = []

    def delete(self, path):
        self.deleted.append(path)


class ActiveSessions:
    def __init__(self):
        self.refresh_count = 0

    def refresh(self):
        self.refresh_count += 1


@pytest.fixture
def context(tmp_path):
    database = Database(tmp_path / "agent.sqlite3")
    repo = Repository(database)
    recycle = RecycleBin()
    workspaces = WorkspaceService(tmp_path / "workspaces", repo, recycle)
    active = ActiveSessions()
    archive = ArchiveService(repo, workspaces, active)
    yield repo, workspaces, recycle, archive
    database.close()


def test_legacy_provider_configs_use_preset_protocol_defaults(tmp_path):
    database = Database(tmp_path / "agent.sqlite3")
    service = ModelService(Repository(database), MemoryCredentials())
    now = datetime.now(UTC)
    openai = ProviderConfig(
        "openai", "OpenAI", "https://example.test/v1", {"models": ["gpt-test"]}, now, now
    )
    deepseek = ProviderConfig(
        "deepseek",
        "DeepSeek",
        "https://example.test/v1",
        {"models": ["deepseek-test"]},
        now,
        now,
    )

    assert service._config_payload(openai)["apiProtocol"] == "responses"
    assert service._config_payload(deepseek)["apiProtocol"] == "chat_completions"
    database.close()


def test_archived_chat_can_be_restored(context):
    repo, workspaces, _, archive = context
    path = workspaces.create_for_session("session-1")
    session = repo.create_session("Draft", str(path))
    repo.archive_session(session.id)
    archive.archived.refresh()
    archive.restore(session.id)
    assert repo.get_session(session.id).status.value == "active"


def test_delete_moves_only_automatic_workspace_then_removes_record(context):
    repo, workspaces, recycle, archive = context
    path = workspaces.create_for_session("session-1")
    external = path.parent.parent / "external"
    external.mkdir()
    session = repo.create_session("Draft", str(path))
    workspaces.associate_external_directory(session.id, external)
    repo.archive_session(session.id)
    archive.deletePermanently(session.id)
    assert recycle.deleted == [path]
    assert external.exists()
    assert repo.get_session(session.id) is None


def test_active_chat_cannot_be_deleted(context):
    repo, workspaces, _, archive = context
    path = workspaces.create_for_session("session-1")
    session = repo.create_session("Draft", str(path))
    with pytest.raises(InvalidSessionState):
        archive.deletePermanently(session.id)


def test_model_config_never_exposes_api_key(tmp_path):
    database = Database(tmp_path / "agent.sqlite3")
    repo = Repository(database)
    credentials = MemoryCredentials()
    service = ModelService(repo, credentials)
    service.saveProvider("openai", "https://example.test/v1", "top-secret", "model-a")
    assert "top-secret" not in str(service.configuredModels)
    assert "top-secret" not in str(repo.get_provider_config("openai"))
    assert credentials.values["openai"] == "top-secret"
    database.close()


def test_same_provider_supports_multiple_instances_models_and_timeouts(tmp_path):
    database = Database(tmp_path / "agent.sqlite3")
    repo = Repository(database)
    credentials = MemoryCredentials()
    service = ModelService(repo, credentials)

    first_id = service.saveProviderConfig(
        "",
        "openai",
        "工作 OpenAI",
        "https://one.test/v1",
        "first-secret",
        45,
        "responses",
        ["model-a", "model-b", "model-a"],
    )
    second_id = service.saveProviderConfig(
        "",
        "openai",
        "备用 OpenAI",
        "https://two.test/v1",
        "second-secret",
        90,
        "chat_completions",
        ["model-c"],
    )

    assert first_id != second_id
    assert len(service.providerConfigs) == 2
    assert repo.get_provider_config(first_id).config == {
        "credential_ref": first_id,
        "models": ["model-a", "model-b"],
        "api_protocol": "responses",
        "provider_type": "openai",
        "timeout": 45,
    }
    assert credentials.values == {
        first_id: "first-secret",
        second_id: "second-secret",
    }
    assert {choice["value"] for choice in service.configuredModels} == {
        f"{first_id}:model-a",
        f"{first_id}:model-b",
        f"{second_id}:model-c",
    }
    database.close()


@pytest.mark.asyncio
async def test_models_dev_metadata_is_provider_scoped_and_preserves_manual_context(
    tmp_path, monkeypatch
):
    database = Database(tmp_path / "agent.sqlite3")
    repo = Repository(database)
    service = ModelService(repo, MemoryCredentials())
    config_id = service.saveProviderConfig(
        "",
        "deepseek",
        "DeepSeek",
        "https://example.test/v1",
        "",
        30,
        "chat_completions",
        ["deepseek-chat", "deepseek-reasoner"],
        {
            "deepseek-chat": {
                "context": 900000,
                "output": 1000,
                "context_source": "manual",
            }
        },
    )

    class Response:
        text = json.dumps(
            {
                "deepseek": {
                    "models": {
                        "deepseek-chat": {"limit": {"context": 1000000, "output": 384000}},
                        "deepseek-reasoner": {"limit": {"context": 1000000, "output": 384000}},
                    }
                },
                "openai": {"models": {"gpt-test": {"limit": {"context": 128000}}}},
            }
        )

        def raise_for_status(self):
            return None

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        async def get(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setattr("desktop_agent.services.httpx.AsyncClient", lambda **_: Client())
    await service._refresh_provider_metadata("deepseek")

    cache = repo.get_app_setting("models_dev_cache:deepseek").value
    assert set(cache["models"]) == {"deepseek-chat", "deepseek-reasoner"}
    saved = repo.get_provider_config(config_id).config["model_settings"]
    assert saved["deepseek-chat"]["context"] == 900000
    assert saved["deepseek-chat"]["output"] == 384000
    assert saved["deepseek-reasoner"] == {
        "context": 1000000,
        "context_source": "models.dev",
        "output": 384000,
    }
    database.close()


@pytest.mark.asyncio
async def test_models_dev_failure_keeps_existing_cache(tmp_path, monkeypatch):
    database = Database(tmp_path / "agent.sqlite3")
    repo = Repository(database)
    service = ModelService(repo, MemoryCredentials())
    repo.set_app_setting(
        "models_dev_cache:deepseek",
        {
            "provider_type": "deepseek",
            "fetched_at": "2020-01-01T00:00:00+00:00",
            "models": {"deepseek-chat": {"context": 1000000, "output": 384000}},
        },
    )

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        async def get(self, *_args, **_kwargs):
            raise httpx.ConnectError("offline")

    import httpx

    monkeypatch.setattr("desktop_agent.services.httpx.AsyncClient", lambda **_: Client())
    await service._refresh_provider_metadata("deepseek")

    cache = repo.get_app_setting("models_dev_cache:deepseek").value
    assert cache["models"]["deepseek-chat"]["context"] == 1000000
    assert cache["failed_at"]
    database.close()


def test_model_context_and_output_accept_large_values(tmp_path):
    database = Database(tmp_path / "agent.sqlite3")
    repo = Repository(database)
    service = ModelService(repo, MemoryCredentials())
    config_id = service.saveProviderConfig(
        "",
        "openai",
        "OpenAI",
        "https://example.test/v1",
        "",
        120,
        "responses",
        ["large-model"],
        {"large-model": {"context": 20000000, "output": 500000}},
    )
    entry = repo.get_provider_config(config_id).config["model_settings"]["large-model"]
    assert entry["context"] == 20000000
    assert entry["output"] == 500000
    assert service._config_payload(repo.get_provider_config(config_id))["modelEntries"][0][
        "contextWindow"
    ] == 20000000
    database.close()


def test_saving_model_metadata_does_not_drop_existing_protocols(tmp_path):
    database = Database(tmp_path / "agent.sqlite3")
    repo = Repository(database)
    service = ModelService(repo, MemoryCredentials())
    config_id = service.saveProviderConfig(
        "",
        "openai",
        "OpenAI",
        "https://example.test/v1",
        "",
        120,
        "responses",
        ["model-a"],
        {"model-a": {"api_protocol": "chat_completions", "context": 128000}},
    )
    service.saveProviderConfig(
        config_id,
        "openai",
        "OpenAI",
        "https://example.test/v1",
        "",
        120,
        "",
        ["model-a"],
        {"model-a": {"context": 256000, "output": 16384}},
    )
    config = repo.get_provider_config(config_id).config
    assert config["api_protocol"] == "responses"
    assert config["model_settings"]["model-a"]["api_protocol"] == "chat_completions"
    database.close()


@pytest.mark.asyncio
async def test_model_connectivity_uses_provider_timeout_and_isolated_clients(
    tmp_path, monkeypatch
):
    database = Database(tmp_path / "agent.sqlite3")
    repo = Repository(database)
    service = ModelService(repo, MemoryCredentials())
    config_id = service.saveProviderConfig(
        "", "openai", "OpenAI", "https://example.test/v1", "", 48, "responses", ["model-a"]
    )
    calls = []

    class TestClient:
        def __init__(self, base_url, api_key, *, timeout, api_protocol):
            calls.append((base_url, api_key, timeout, api_protocol))

        async def discover_models(self):
            calls.append("discover")
            return ["model-a", "model-b"]

        async def stream_chat(self, **request):
            calls.append(("stream", request))
            yield object()

        async def close(self):
            calls.append("closed")

    monkeypatch.setattr("desktop_agent.services.OpenAICompatibleClient", TestClient)
    clock = iter((10.0, 10.1234, 20.0, 20.08))
    monkeypatch.setattr("desktop_agent.services.perf_counter", lambda: next(clock))
    results = []
    service.modelTestFinished.connect(
        lambda provider, model, ok, message: results.append((provider, model, ok, message))
    )

    await service._test_model(config_id, "model-a")
    await service._test_model(config_id, "model-a")

    assert calls[0] == ("https://example.test/v1", None, 48, "responses")
    assert calls.count("discover") == 2
    assert sum(call[0] == "stream" for call in calls if isinstance(call, tuple)) == 2
    assert calls.count("closed") == 2
    assert results == [
        (config_id, "model-a", True, "123ms"),
        (config_id, "model-a", True, "80ms"),
    ]
    database.close()


@pytest.mark.asyncio
async def test_model_warmup_is_background_and_deduplicated(tmp_path, monkeypatch):
    database = Database(tmp_path / "agent.sqlite3")
    repo = Repository(database)
    service = ModelService(repo, MemoryCredentials())
    config_id = service.saveProviderConfig(
        "", "openai", "OpenAI", "https://example.test/v1", "", 120, "responses", ["model-a"]
    )
    calls = []

    class WarmClient:
        def __init__(self, base_url, api_key, *, timeout, api_protocol):
            calls.append("created")

        async def close(self):
            calls.append("closed")

    monkeypatch.setattr("desktop_agent.services.OpenAICompatibleClient", WarmClient)

    service.warmModel(f"{config_id}:model-a")
    while service._tasks:
        await asyncio.sleep(0)
    service.warmModel(f"{config_id}:model-a")
    await asyncio.sleep(0)

    assert calls == ["created"]
    await service.closeAllClients()
    assert calls[-1] == "closed"
    database.close()


def test_system_prompt_reset_restores_packaged_default(tmp_path):
    database = Database(tmp_path / "agent.sqlite3")
    service = SettingsService(Repository(database))
    service.saveSystemPrompt("custom")
    service.resetSystemPrompt()
    assert service.systemPrompt == default_system_prompt()
    database.close()
