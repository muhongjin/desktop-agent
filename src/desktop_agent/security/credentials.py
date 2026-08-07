from typing import Protocol

import keyring


class CredentialStore(Protocol):
    def get(self, provider_id: str) -> str | None: ...

    def set(self, provider_id: str, secret: str) -> None: ...

    def delete(self, provider_id: str) -> None: ...


class KeyringCredentialStore:
    def __init__(self, service_name: str = "DesktopAgent"):
        self.service_name = service_name

    def get(self, provider_id: str) -> str | None:
        return keyring.get_password(self.service_name, provider_id)

    def set(self, provider_id: str, secret: str) -> None:
        keyring.set_password(self.service_name, provider_id, secret)

    def delete(self, provider_id: str) -> None:
        keyring.delete_password(self.service_name, provider_id)
