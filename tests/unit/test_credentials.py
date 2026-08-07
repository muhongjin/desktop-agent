from desktop_agent.security.credentials import CredentialStore, KeyringCredentialStore


class MemoryCredentials:
    def __init__(self):
        self.values = {}

    def get(self, provider_id):
        return self.values.get(provider_id)

    def set(self, provider_id, secret):
        self.values[provider_id] = secret

    def delete(self, provider_id):
        self.values.pop(provider_id, None)


def test_credential_store_contract_can_use_in_memory_double():
    store: CredentialStore = MemoryCredentials()
    assert store.get("openai") is None
    store.set("openai", "secret")
    assert store.get("openai") == "secret"
    store.delete("openai")
    assert store.get("openai") is None


def test_keyring_adapter_uses_service_and_provider_ids(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "desktop_agent.security.credentials.keyring.get_password",
        lambda service, provider: calls.append(("get", service, provider)) or "stored",
    )
    monkeypatch.setattr(
        "desktop_agent.security.credentials.keyring.set_password",
        lambda service, provider, secret: calls.append(("set", service, provider, secret)),
    )
    monkeypatch.setattr(
        "desktop_agent.security.credentials.keyring.delete_password",
        lambda service, provider: calls.append(("delete", service, provider)),
    )
    store = KeyringCredentialStore("TestAgent")
    assert store.get("openai") == "stored"
    store.set("openai", "secret")
    store.delete("openai")
    assert calls == [
        ("get", "TestAgent", "openai"),
        ("set", "TestAgent", "openai", "secret"),
        ("delete", "TestAgent", "openai"),
    ]
