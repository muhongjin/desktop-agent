from pathlib import Path

from desktop_agent.security.permissions import (
    PermissionBroker,
    PermissionDecision,
    PermissionRequest,
    SessionAccess,
)


def test_none_allows_read_but_rejects_write(tmp_path):
    broker = PermissionBroker()
    read = broker.evaluate(
        PermissionRequest("fs.read", tmp_path / "a.txt"), SessionAccess.none(tmp_path)
    )
    write = broker.evaluate(
        PermissionRequest("fs.write", tmp_path / "a.txt"), SessionAccess.none(tmp_path)
    )
    assert read is PermissionDecision.ALLOW
    assert write is PermissionDecision.DENY


def test_none_rejects_high_risk_command_without_confirmation(tmp_path):
    request = PermissionRequest("process.exec", tmp_path, risk="system-change")
    assert (
        PermissionBroker().evaluate(request, SessionAccess.none(tmp_path))
        is PermissionDecision.DENY
    )


def test_local_allows_workspace_write(tmp_path):
    broker = PermissionBroker()
    request = PermissionRequest("fs.write", tmp_path / "a.txt")
    assert broker.evaluate(request, SessionAccess.local(tmp_path)) is PermissionDecision.ALLOW


def test_associated_directory_is_trusted(tmp_path):
    workspace = tmp_path / "session"
    external = tmp_path / "project"
    request = PermissionRequest("fs.write", external / "a.txt")
    access = SessionAccess.local(workspace, associated_directory=external)
    assert PermissionBroker().evaluate(request, access) is PermissionDecision.ALLOW


def test_local_rejects_path_traversal(tmp_path):
    workspace = tmp_path / "session"
    request = PermissionRequest("fs.read", workspace / ".." / "secret.txt")
    assert (
        PermissionBroker().evaluate(request, SessionAccess.local(workspace))
        is PermissionDecision.DENY
    )


def test_full_access_removes_path_restriction(tmp_path):
    request = PermissionRequest("fs.write", tmp_path / "outside" / "a.txt")
    access = SessionAccess.full_access(tmp_path / "session")
    assert PermissionBroker().evaluate(request, access) is PermissionDecision.ALLOW


def test_full_access_still_confirms_system_change():
    request = PermissionRequest("process.exec", Path("C:/Windows/System32"), risk="system-change")
    access = SessionAccess.full_access(Path("C:/session"))
    assert PermissionBroker().evaluate(request, access) is PermissionDecision.CONFIRM


def test_delete_requires_confirmation_even_in_workspace(tmp_path):
    request = PermissionRequest("fs.delete", tmp_path / "a.txt")
    assert (
        PermissionBroker().evaluate(request, SessionAccess.local(tmp_path))
        is PermissionDecision.CONFIRM
    )
