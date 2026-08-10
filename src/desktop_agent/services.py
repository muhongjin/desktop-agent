import asyncio
import json
import os
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import httpx
from keyring.errors import KeyringError
from PySide6.QtCore import Property, QAbstractListModel, QModelIndex, QObject, Qt, Signal, Slot

from desktop_agent.domain.models import ProviderConfig, SessionStatus
from desktop_agent.providers.openai_compatible import (
    ModelDiscoveryError,
    OpenAICompatibleClient,
    ProviderError,
)
from desktop_agent.providers.presets import PRESETS_BY_ID, PROVIDER_PRESETS


def default_system_prompt() -> str:
    return (
        files("desktop_agent.resources")
        .joinpath("default_system_prompt.md")
        .read_text(encoding="utf-8")
        .strip()
    )


class SettingsService(QObject):
    systemPromptChanged = Signal()
    settingsChanged = Signal()

    def __init__(self, repository, data_dir: Path | None = None):
        super().__init__()
        self.repository = repository
        self.data_dir = data_dir

    def get(self, key: str, default=None):
        setting = self.repository.get_app_setting(key)
        return default if setting is None else setting.value

    @Property(str, notify=systemPromptChanged)
    def systemPrompt(self):
        return self.get("system_prompt", default_system_prompt())

    @Property(str, notify=settingsChanged)
    def theme(self):
        return self.get("theme", "system")

    @Property(str, notify=settingsChanged)
    def shellMode(self):
        return self.get("shell_mode", "auto")

    @Property(bool, notify=settingsChanged)
    def startAtLogin(self):
        return bool(self.get("start_at_login", False))

    @Property(str, notify=settingsChanged)
    def logDirectory(self):
        fallback = str(self.data_dir / "logs") if self.data_dir is not None else ""
        return self.get("log_directory", fallback)

    @Slot(str)
    def saveSystemPrompt(self, value: str) -> None:
        self.repository.set_app_setting("system_prompt", value)
        self.systemPromptChanged.emit()

    @Slot()
    def resetSystemPrompt(self) -> None:
        self.repository.set_app_setting("system_prompt", default_system_prompt())
        self.systemPromptChanged.emit()

    @Slot(str, object)
    def setValue(self, key: str, value) -> None:
        self.repository.set_app_setting(key, value)
        self.settingsChanged.emit()


class ModelService(QObject):
    configuredModelsChanged = Signal()
    providerConfigsChanged = Signal()
    modelsDiscovered = Signal(str, list)
    discoveryFailed = Signal(str, str)
    modelTestFinished = Signal(str, str, bool, str)
    modelProbeFinished = Signal(str, str, bool, str, str)
    modelMetadataChanged = Signal(str)

    def __init__(self, repository, credentials):
        super().__init__()
        self.repository = repository
        self.credentials = credentials
        self._tasks: set[asyncio.Task] = set()
        self._clients: dict[str, tuple[tuple[str, int, str], OpenAICompatibleClient]] = {}
        self._retired_clients: list[OpenAICompatibleClient] = []
        self._warmed_clients: set[str] = set()
        self._warming_clients: set[str] = set()
        self._client_lock = asyncio.Lock()
        self._metadata_tasks: dict[str, asyncio.Task] = {}

    _METADATA_URL = "https://models.dev/api.json"
    _METADATA_TTL_SECONDS = 24 * 60 * 60
    _METADATA_RETRY_SECONDS = 6 * 60 * 60

    @Property(list, constant=True)
    def providerPresets(self):
        return [
            {
                "id": preset.id,
                "displayName": preset.display_name,
                "baseUrl": preset.base_url,
                "modelHints": list(preset.model_hints),
                "accentColor": preset.accent_color,
                "mark": preset.mark,
                "apiProtocol": preset.api_protocol,
            }
            for preset in PROVIDER_PRESETS
        ]

    @Property(list, notify=providerConfigsChanged)
    def providerConfigs(self):
        return [self._config_payload(config) for config in self.repository.list_provider_configs()]

    @Property(list, notify=configuredModelsChanged)
    def configuredModels(self):
        choices = []
        for config in self.repository.list_provider_configs():
            settings = config.config.get("model_settings", {})
            for model_id in config.config.get("models", []):
                model_settings = settings.get(model_id, {})
                if isinstance(model_settings, dict) and model_settings.get("enabled") is False:
                    continue
                choices.append(
                    {
                        "display": f"{model_id} · {config.display_name}",
                        "value": f"{config.provider_id}:{model_id}",
                    }
                )
        return choices or [{"display": "请先配置模型", "value": ""}]

    def _config_payload(self, config: ProviderConfig) -> dict:
        provider_type = config.config.get("provider_type", config.provider_id)
        preset = PRESETS_BY_ID.get(provider_type, PRESETS_BY_ID["custom"])
        models = [
            model_id
            for model_id in config.config.get("models", [])
            if isinstance(model_id, str) and model_id.strip()
        ]
        raw_settings = config.config.get("model_settings", {})
        model_entries = []
        for model_id in models:
            values = raw_settings.get(model_id, {})
            if not isinstance(values, dict):
                values = {}
            context_value = self._token_limit(values.get("context", values.get("context_window")))
            model_protocol = values.get("api_protocol")
            if model_protocol not in {"chat_completions", "responses"}:
                model_protocol = self._config_protocol(config)
            model_entries.append(
                {
                    "id": model_id,
                    "enabled": bool(values.get("enabled", True)),
                    "capabilities": str(values.get("capabilities", "")),
                    "contextWindow": context_value or 0,
                    "outputTokens": self._token_limit(values.get("output")) or 0,
                    "contextKnown": context_value is not None and context_value > 0,
                    "contextSource": self._context_source(values),
                    "apiProtocol": model_protocol,
                }
            )
        return {
            "id": config.provider_id,
            "providerId": preset.id,
            "providerName": preset.display_name,
            "displayName": config.display_name,
            "baseUrl": config.base_url,
            "models": models,
            "modelEntries": model_entries,
            "timeout": self._timeout(config.config.get("timeout", 120)),
            "apiProtocol": self._config_protocol(config),
            "accentColor": preset.accent_color,
            "mark": preset.mark,
        }

    @staticmethod
    def _timeout(value) -> int:
        try:
            return max(1, min(600, int(value)))
        except (TypeError, ValueError):
            return 120

    @staticmethod
    def _context_window(value) -> int:
        return ModelService._token_limit(value) or 0

    @staticmethod
    def _token_limit(value) -> int | None:
        if value is None or value == "":
            return None
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            return None
        return normalized if normalized >= 0 else None

    @staticmethod
    def _context_source(values: dict) -> str:
        source = values.get("context_source")
        if source in {"manual", "models.dev", "unknown"}:
            return source
        legacy = values.get("context_window", values.get("context"))
        return "manual" if ModelService._token_limit(legacy) not in {None, 0} else "unknown"

    @staticmethod
    def _api_protocol(value, provider_type: str) -> str:
        if value in {"chat_completions", "responses"}:
            return value
        preset = PRESETS_BY_ID.get(provider_type, PRESETS_BY_ID["custom"])
        return preset.api_protocol

    @classmethod
    def _config_protocol(cls, config: ProviderConfig) -> str:
        provider_type = config.config.get("provider_type", config.provider_id)
        return cls._api_protocol(config.config.get("api_protocol"), provider_type)

    @staticmethod
    def _models(values) -> list[str]:
        models = []
        for value in values or []:
            model_id = str(value).strip()
            if model_id and model_id not in models:
                models.append(model_id)
        return models

    @classmethod
    def _model_settings(cls, values, models: list[str]) -> dict[str, dict]:
        if not isinstance(values, dict):
            return {}
        normalized = {}
        for model_id in models:
            item = values.get(model_id)
            if not isinstance(item, dict):
                continue
            normalized[model_id] = {
                "enabled": bool(item.get("enabled", True)),
                "capabilities": str(item.get("capabilities", "")),
                "context": cls._token_limit(item.get("context", item.get("context_window"))),
                "output": cls._token_limit(item.get("output")),
                "context_source": cls._context_source(item),
                "api_protocol": item.get("api_protocol")
                if item.get("api_protocol") in {"chat_completions", "responses"}
                else None,
            }
        return normalized

    def _changed(self) -> None:
        self.providerConfigsChanged.emit()
        self.configuredModelsChanged.emit()

    @Slot(str, str, str, str, str, int, str, list, dict, result=str)
    def saveProviderConfig(
        self,
        config_id: str,
        provider_type: str,
        display_name: str,
        base_url: str,
        api_key: str,
        timeout: int,
        api_protocol: str,
        models: list,
        model_settings: dict | None = None,
    ) -> str:
        preset = PRESETS_BY_ID.get(provider_type, PRESETS_BY_ID["custom"])
        config_id = config_id.strip() or str(uuid4())
        existing = self.repository.get_provider_config(config_id)
        now = datetime.now(UTC)
        normalized_models = self._models(models)
        config_values = {
            "provider_type": preset.id,
            "models": normalized_models,
            "timeout": self._timeout(timeout),
            "credential_ref": config_id,
        }
        if api_protocol in {"chat_completions", "responses"}:
            config_values["api_protocol"] = self._api_protocol(api_protocol, preset.id)
        elif existing is not None and existing.config.get("provider_type", existing.provider_id) == preset.id:
            previous_protocol = existing.config.get("api_protocol")
            if previous_protocol in {"chat_completions", "responses"}:
                config_values["api_protocol"] = previous_protocol
        normalized_settings = self._model_settings(model_settings, normalized_models)
        previous_settings = existing.config.get("model_settings", {}) if existing else {}
        if isinstance(previous_settings, dict):
            for model_id, item in normalized_settings.items():
                previous = previous_settings.get(model_id)
                if not isinstance(previous, dict):
                    continue
                if item.get("api_protocol") not in {"chat_completions", "responses"}:
                    previous_protocol = previous.get("api_protocol")
                    if previous_protocol in {"chat_completions", "responses"}:
                        item["api_protocol"] = previous_protocol
        if normalized_settings:
            config_values["model_settings"] = normalized_settings
        self.repository.set_provider_config(
            ProviderConfig(
                provider_id=config_id,
                display_name=display_name.strip() or preset.display_name,
                base_url=base_url.strip() or preset.base_url,
                config={
                    "provider_type": preset.id,
                    **config_values,
                },
                created_at=existing.created_at if existing else now,
                updated_at=now,
            )
        )
        if api_key:
            self.credentials.set(config_id, api_key)
        self._invalidate_client(config_id)
        self._changed()
        return config_id

    @staticmethod
    def _metadata_key(provider_type: str) -> str:
        return f"models_dev_cache:{provider_type}"

    def _metadata_cache(self, provider_type: str) -> dict:
        value = self.repository.get_app_setting(self._metadata_key(provider_type))
        return value.value if value is not None and isinstance(value.value, dict) else {}

    @staticmethod
    def _metadata_time(value) -> datetime | None:
        if not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    def _metadata_is_fresh(self, cache: dict) -> bool:
        fetched_at = self._metadata_time(cache.get("fetched_at"))
        if fetched_at is None:
            return False
        return (datetime.now(UTC) - fetched_at).total_seconds() < self._METADATA_TTL_SECONDS

    def _metadata_in_retry_cooldown(self, cache: dict) -> bool:
        failed_at = self._metadata_time(cache.get("failed_at"))
        if failed_at is None:
            return False
        return (datetime.now(UTC) - failed_at).total_seconds() < self._METADATA_RETRY_SECONDS

    @staticmethod
    def _normalize_metadata(payload) -> dict[str, dict[str, int | None]]:
        if not isinstance(payload, dict):
            return {}
        normalized = {}
        for model_id, model in payload.items():
            if not isinstance(model_id, str) or not isinstance(model, dict):
                continue
            limits = model.get("limit")
            if not isinstance(limits, dict):
                continue
            context = ModelService._token_limit(limits.get("context"))
            output = ModelService._token_limit(limits.get("output"))
            if context is None and output is None:
                continue
            normalized[model_id] = {"context": context, "output": output}
        return normalized

    @Slot(str)
    def ensureProviderMetadata(self, provider_type: str) -> None:
        provider_type = (provider_type or "").strip()
        if not provider_type or provider_type == "custom":
            return
        cache = self._metadata_cache(provider_type)
        if self._metadata_is_fresh(cache) or self._metadata_in_retry_cooldown(cache):
            return
        if provider_type in self._metadata_tasks and not self._metadata_tasks[provider_type].done():
            return
        try:
            task = asyncio.create_task(self._refresh_provider_metadata(provider_type))
        except RuntimeError:
            return
        self._metadata_tasks[provider_type] = task
        task.add_done_callback(lambda _: self._metadata_tasks.pop(provider_type, None))

    @Slot(str)
    def startMetadataRefresh(self, provider_type: str = "") -> None:
        if provider_type.strip():
            self.ensureProviderMetadata(provider_type)

    @Slot(str, str, result="QVariantMap")
    def metadataForModel(self, provider_type: str, model_id: str) -> dict:
        models = self._metadata_cache(provider_type).get("models", {})
        item = models.get(model_id, {}) if isinstance(models, dict) else {}
        return item if isinstance(item, dict) else {}

    async def _refresh_provider_metadata(self, provider_type: str) -> None:
        cache = self._metadata_cache(provider_type)
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(10.0, connect=3.0),
                follow_redirects=True,
            ) as client:
                response = await client.get(self._METADATA_URL)
                response.raise_for_status()
                payload = await asyncio.to_thread(json.loads, response.text)
            provider = payload.get(provider_type, {}) if isinstance(payload, dict) else {}
            if not isinstance(provider, dict) or not isinstance(provider.get("models"), dict):
                raise TypeError("Provider metadata is unavailable")
            models = self._normalize_metadata(provider.get("models", {}))
            self.repository.set_app_setting(
                self._metadata_key(provider_type),
                {
                    "provider_type": provider_type,
                    "fetched_at": datetime.now(UTC).isoformat(),
                    "models": models,
                },
            )
            self._apply_provider_metadata(provider_type, models)
            self.modelMetadataChanged.emit(provider_type)
        except (httpx.HTTPError, ValueError, TypeError, OSError):
            failed = dict(cache)
            failed["failed_at"] = datetime.now(UTC).isoformat()
            self.repository.set_app_setting(self._metadata_key(provider_type), failed)

    def _apply_provider_metadata(self, provider_type: str, metadata: dict) -> None:
        configs_changed = False
        for config in self.repository.list_provider_configs():
            current_type = config.config.get("provider_type", config.provider_id)
            if current_type != provider_type:
                continue
            settings = dict(config.config.get("model_settings", {}))
            changed = False
            for model_id in self._models(config.config.get("models", [])):
                item = metadata.get(model_id)
                if not isinstance(item, dict):
                    continue
                current = settings.get(model_id, {})
                if not isinstance(current, dict):
                    current = {}
                values = dict(current)
                if self._context_source(current) != "manual" and item.get("context") is not None:
                    values["context"] = item["context"]
                    values["context_source"] = "models.dev"
                if item.get("output") is not None:
                    values["output"] = item["output"]
                if values == current:
                    continue
                settings[model_id] = values
                changed = True
            if not changed:
                continue
            values = dict(config.config)
            values["model_settings"] = settings
            self.repository.set_provider_config(
                ProviderConfig(
                    provider_id=config.provider_id,
                    display_name=config.display_name,
                    base_url=config.base_url,
                    config=values,
                    created_at=config.created_at,
                    updated_at=datetime.now(UTC),
                )
            )
            configs_changed = True
        if configs_changed:
            self.providerConfigsChanged.emit()

    @Slot(str)
    def deleteProviderConfig(self, config_id: str) -> None:
        config_id = config_id.strip()
        if not config_id:
            return
        self._invalidate_client(config_id)
        try:
            self.credentials.delete(config_id)
        except (KeyringError, OSError):
            pass
        self.repository.delete_provider_config(config_id)
        self._changed()

    @Slot(str, str, bool)
    def setModelEnabled(self, config_id: str, model_id: str, enabled: bool) -> None:
        config = self.repository.get_provider_config(config_id)
        if config is None or not model_id.strip():
            return
        models = self._models(config.config.get("models", []))
        if model_id not in models:
            return
        settings = dict(config.config.get("model_settings", {}))
        current = settings.get(model_id, {})
        if not isinstance(current, dict):
            current = {}
        settings[model_id] = {**current, "enabled": bool(enabled)}
        values = dict(config.config)
        values["model_settings"] = settings
        self.repository.set_provider_config(
            ProviderConfig(
                provider_id=config.provider_id,
                display_name=config.display_name,
                base_url=config.base_url,
                config=values,
                created_at=config.created_at,
                updated_at=datetime.now(UTC),
            )
        )
        self._changed()

    def _invalidate_client(self, config_id: str) -> None:
        self._warmed_clients.discard(config_id)
        entry = self._clients.pop(config_id, None)
        if entry is not None:
            self._retired_clients.append(entry[1])

    async def clientFor(
        self, config_id: str, config=None, model_id: str | None = None
    ) -> OpenAICompatibleClient:
        config = config or self.repository.get_provider_config(config_id)
        if config is None:
            raise KeyError(f"Unknown provider config: {config_id}")
        if model_id:
            model_settings = config.config.get("model_settings", {}).get(model_id, {})
            if isinstance(model_settings, dict) and model_settings.get("enabled") is False:
                raise RuntimeError("模型已停用")
        timeout = self._timeout(config.config.get("timeout", 120))
        api_protocol = self._config_protocol(config)
        if model_id:
            model_settings = config.config.get("model_settings", {}).get(model_id, {})
            if isinstance(model_settings, dict):
                model_protocol = model_settings.get("api_protocol")
                if model_protocol in {"chat_completions", "responses"}:
                    api_protocol = model_protocol
        signature = (config.base_url, timeout, api_protocol)
        async with self._client_lock:
            entry = self._clients.get(config_id)
            if entry is not None and entry[0] == signature:
                return entry[1]
            if entry is not None:
                self._retired_clients.append(entry[1])
            secret = await asyncio.to_thread(self.credentials.get, config_id)
            client = OpenAICompatibleClient(
                config.base_url,
                secret,
                timeout=timeout,
                api_protocol=api_protocol,
            )
            self._clients[config_id] = (signature, client)
            return client

    async def _close_retired_clients(self) -> None:
        retired, self._retired_clients = self._retired_clients, []
        for client in retired:
            await client.close()

    async def closeAllClients(self) -> None:
        metadata_tasks = list(self._metadata_tasks.values())
        self._metadata_tasks.clear()
        for task in metadata_tasks:
            task.cancel()
        if metadata_tasks:
            await asyncio.gather(*metadata_tasks, return_exceptions=True)
        async with self._client_lock:
            await self._close_retired_clients()
            clients = [entry[1] for entry in self._clients.values()]
            self._clients.clear()
            self._warmed_clients.clear()
            for client in clients:
                await client.close()

    @Slot()
    def closeClients(self) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        task = loop.create_task(self.closeAllClients())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    @Slot(str)
    def warmModel(self, model_value: str) -> None:
        if ":" not in model_value:
            return
        config_id, _ = model_value.split(":", 1)
        if config_id in self._warmed_clients or config_id in self._warming_clients:
            return
        if self.repository.get_provider_config(config_id) is None:
            return
        self._warming_clients.add(config_id)
        task = asyncio.create_task(self._warm_client(config_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _warm_client(self, config_id: str) -> None:
        try:
            await self.clientFor(config_id)
            self._warmed_clients.add(config_id)
        except (KeyringError, OSError, RuntimeError):
            pass
        finally:
            self._warming_clients.discard(config_id)

    @Slot(str, str, str, str)
    def saveProvider(self, provider_id: str, base_url: str, api_key: str, model_id: str) -> None:
        preset = PRESETS_BY_ID[provider_id]
        self.saveProviderConfig(
            provider_id,
            provider_id,
            preset.display_name,
            base_url,
            api_key,
            120,
            preset.api_protocol,
            [model_id] if model_id.strip() else [],
        )

    @Slot(str, str, str, str, str, int)
    def discoverModels(
        self,
        request_id: str,
        config_id: str,
        provider_type: str,
        base_url: str,
        api_key: str,
        timeout: int,
    ) -> None:
        task = asyncio.create_task(
            self._discover(request_id, config_id, provider_type, base_url, api_key, timeout)
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _discover(
        self,
        request_id: str,
        config_id: str,
        provider_type: str,
        base_url: str,
        api_key: str,
        timeout: int,
    ) -> None:
        preset = PRESETS_BY_ID.get(provider_type, PRESETS_BY_ID["custom"])
        resolved_url = base_url.strip() or preset.base_url
        secret = api_key or (
            await asyncio.to_thread(self.credentials.get, config_id) if config_id else None
        )
        client = OpenAICompatibleClient(resolved_url, secret, timeout=self._timeout(timeout))
        try:
            models = await client.discover_models()
            self.modelsDiscovered.emit(request_id, models)
        except ModelDiscoveryError as error:
            self.discoveryFailed.emit(request_id, str(error))
        finally:
            await client.close()

    @Slot(str, str)
    def testModel(self, config_id: str, model_id: str) -> None:
        task = asyncio.create_task(self._test_model(config_id, model_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    @Slot(str, str, str, str, str, int, str, str)
    def probeModel(
        self,
        request_id: str,
        provider_type: str,
        base_url: str,
        api_key: str,
        model_id: str,
        timeout: int,
        preferred_protocol: str = "responses",
        config_id: str = "",
    ) -> None:
        task = asyncio.create_task(
            self._probe_model(
                request_id,
                provider_type,
                base_url,
                api_key,
                model_id,
                timeout,
                preferred_protocol,
                config_id,
            )
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _probe_model(
        self,
        request_id: str,
        provider_type: str,
        base_url: str,
        api_key: str,
        model_id: str,
        timeout: int,
        preferred_protocol: str,
        config_id: str,
    ) -> None:
        try:
            protocol, last_error, elapsed_ms = await self._probe_protocol(
                provider_type,
                base_url,
                model_id,
                timeout,
                config_id if not api_key else "",
                api_key or None,
            )
        except (KeyringError, OSError, RuntimeError) as error:
            self.modelProbeFinished.emit(request_id, model_id, False, str(error), "")
            return
        if protocol:
            self.modelProbeFinished.emit(request_id, model_id, True, f"{elapsed_ms}ms", protocol)
            return
        self.modelProbeFinished.emit(request_id, model_id, False, last_error, "")

    async def _probe_protocol(
        self,
        provider_type: str,
        base_url: str,
        model_id: str,
        timeout: int,
        config_id: str = "",
        secret: str | None = None,
    ) -> tuple[str | None, str, int | None]:
        preset = PRESETS_BY_ID.get(provider_type, PRESETS_BY_ID["custom"])
        secret = secret or (
            await asyncio.to_thread(self.credentials.get, config_id) if config_id else None
        )
        last_error = "模型测试失败"
        for protocol in ("responses", "chat_completions"):
            client = OpenAICompatibleClient(
                base_url.strip() or preset.base_url,
                secret,
                timeout=self._timeout(timeout),
                api_protocol=protocol,
            )
            try:
                started = perf_counter()
                received = False
                async for _ in client.stream_chat(
                    model_id=model_id,
                    messages=({"role": "user", "content": "Reply with OK only."},),
                ):
                    received = True
                    break
                if not received:
                    raise ProviderError("Provider returned an empty response")
                elapsed_ms = max(1, round((perf_counter() - started) * 1000))
                return protocol, "", elapsed_ms
            except (ModelDiscoveryError, OSError, ProviderError, RuntimeError) as error:
                last_error = str(error)
            finally:
                await client.close()
        return None, last_error, None

    async def _test_model(self, config_id: str, model_id: str) -> None:
        config = self.repository.get_provider_config(config_id)
        if config is None:
            self.modelTestFinished.emit(config_id, model_id, False, "配置不存在")
            return
        client = None
        try:
            secret = await asyncio.to_thread(self.credentials.get, config_id)
            client = OpenAICompatibleClient(
                config.base_url,
                secret,
                timeout=self._timeout(config.config.get("timeout", 120)),
                api_protocol="responses",
            )
            models = await client.discover_models()
            if model_id not in models:
                self.modelTestFinished.emit(
                    config_id,
                    model_id,
                    False,
                    "模型未出现在服务商返回的列表中",
                )
                return
            last_error = "模型测试失败"
            for protocol in ("responses", "chat_completions"):
                if protocol == "chat_completions":
                    await client.close()
                    client = OpenAICompatibleClient(
                        config.base_url,
                        secret,
                        timeout=self._timeout(config.config.get("timeout", 120)),
                        api_protocol=protocol,
                    )
                try:
                    started = perf_counter()
                    received = False
                    async for _ in client.stream_chat(
                        model_id=model_id,
                        messages=({"role": "user", "content": "Reply with OK only."},),
                    ):
                        received = True
                        break
                    if not received:
                        raise ProviderError("Provider returned an empty response")
                    elapsed_ms = max(1, round((perf_counter() - started) * 1000))
                    self.modelTestFinished.emit(config_id, model_id, True, f"{elapsed_ms}ms")
                    return
                except (ModelDiscoveryError, OSError, ProviderError, RuntimeError) as error:
                    last_error = str(error)
            self.modelTestFinished.emit(config_id, model_id, False, last_error)
        except (KeyringError, ModelDiscoveryError, OSError, ProviderError, RuntimeError) as error:
            self.modelTestFinished.emit(config_id, model_id, False, str(error))
        finally:
            if client is not None:
                await client.close()


class ArchivedSessionModel(QAbstractListModel):
    IdRole = Qt.UserRole + 1
    TitleRole = Qt.UserRole + 2

    def __init__(self, repository):
        super().__init__()
        self.repository = repository
        self.sessions = []
        self.refresh()

    def roleNames(self):
        return {self.IdRole: b"sessionId", self.TitleRole: b"title"}

    def rowCount(self, parent=None):
        parent = parent or QModelIndex()
        return 0 if parent.isValid() else len(self.sessions)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.sessions):
            return None
        session = self.sessions[index.row()]
        if role == self.IdRole:
            return session.id
        if role in {self.TitleRole, Qt.DisplayRole}:
            return session.title
        return None

    def refresh(self) -> None:
        self.beginResetModel()
        self.sessions = self.repository.list_sessions(SessionStatus.ARCHIVED)
        self.endResetModel()


class ArchiveService(QObject):
    changed = Signal()

    def __init__(self, repository, workspaces, active_sessions):
        super().__init__()
        self.repository = repository
        self.workspaces = workspaces
        self.active_sessions = active_sessions
        self.archived = ArchivedSessionModel(repository)

    @Property(QObject, constant=True)
    def archivedSessions(self):
        return self.archived

    @Slot(str)
    def restore(self, session_id: str) -> None:
        self.repository.restore_session(session_id)
        self.archived.refresh()
        self.active_sessions.refresh()
        self.changed.emit()

    @Slot(str)
    def deletePermanently(self, session_id: str) -> None:
        self.workspaces.delete_archived_workspace(session_id)
        self.repository.delete_session(session_id)
        self.archived.refresh()
        self.changed.emit()


class DataService(QObject):
    def __init__(self, data_dir: Path, workspaces_dir: Path):
        super().__init__()
        self.data_dir = data_dir
        self.workspaces_dir = workspaces_dir

    @Property(str, constant=True)
    def dataPath(self):
        return str(self.data_dir)

    @Property(str, constant=True)
    def workspacesPath(self):
        return str(self.workspaces_dir)

    @Slot()
    def openDataDirectory(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(self.data_dir)

    @Slot()
    def openWorkspacesDirectory(self) -> None:
        self.workspaces_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(self.workspaces_dir)
