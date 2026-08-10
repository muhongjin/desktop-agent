from typing import Protocol

import keyring


class CredentialStore(Protocol):
    def get(self, provider_id: str) -> str | None: ...

    def set(self, provider_id: str, secret: str) -> None: ...

    def delete(self, provider_id: str) -> None: ...


class KeyringCredentialStore:
    def __init__(self, service_name: str = "DesktopAgent"):
        self.service_name = service_name
        self._cache: dict[str, str | None] = {}

    def get(self, provider_id: str) -> str | None:
        if provider_id not in self._cache:
            self._cache[provider_id] = keyring.get_password(self.service_name, provider_id)
        return self._cache[provider_id]

    def set(self, provider_id: str, secret: str) -> None:
        keyring.set_password(self.service_name, provider_id, secret)
        self._cache[provider_id] = secret

    def delete(self, provider_id: str) -> None:
        keyring.delete_password(self.service_name, provider_id)
        self._cache.pop(provider_id, None)
