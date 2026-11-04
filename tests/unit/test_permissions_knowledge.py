from __future__ import annotations

from pathlib import Path

from desktop_agent.security.permissions import (
    PermissionBroker,
    PermissionDecision,
    PermissionRequest,
    SessionAccess,
)


def test_kb_read_is_allowed_only_when_bases_are_selected():
    broker = PermissionBroker()
    workspace = Path("C:/tmp/workspace")
    access = SessionAccess.local(workspace, knowledge_kb_ids=frozenset({"kb-1"}))
    request = PermissionRequest("kb.read", workspace)
    assert broker.evaluate(request, access) is PermissionDecision.ALLOW


def test_kb_read_is_denied_without_selection():
    broker = PermissionBroker()
    workspace = Path("C:/tmp/workspace")
    access = SessionAccess.local(workspace)
    request = PermissionRequest("kb.read", workspace)
    assert broker.evaluate(request, access) is PermissionDecision.DENY


def test_kb_read_ignores_execution_mode_path_rules():
    broker = PermissionBroker()
    workspace = Path("C:/tmp/workspace")
    access = SessionAccess.none(workspace, knowledge_kb_ids=frozenset({"kb-1"}))
    request = PermissionRequest("kb.read", Path("D:/elsewhere"))
    assert broker.evaluate(request, access) is PermissionDecision.ALLOW
