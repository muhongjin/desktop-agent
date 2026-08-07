import os

import pytest

from desktop_agent.security.permissions import PermissionBroker, SessionAccess
from desktop_agent.tools.files import FileTools, PermissionConfirmationRequired, PermissionDenied
from desktop_agent.tools.registry import file_tool_registry


@pytest.fixture
def files(tmp_path):
    return FileTools(PermissionBroker(), SessionAccess.local(tmp_path))


def test_write_uses_temp_file_then_replace(files, tmp_path):
    target = tmp_path / "a.txt"
    result = files.write_file(target, "new content")
    assert target.read_text() == "new content"
    assert result.byte_count == 11
    assert list(target.parent.glob(f".{target.name}.*.tmp")) == []


def test_failed_replace_removes_temporary_file(files, tmp_path, monkeypatch):
    target = tmp_path / "a.txt"

    def fail_replace(source, destination):
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(OSError, match="replace failed"):
        files.write_file(target, "content")
    assert list(tmp_path.glob(".a.txt.*.tmp")) == []


def test_path_outside_workspace_is_rejected(files, tmp_path):
    with pytest.raises(PermissionDenied):
        files.write_file(tmp_path.parent / "outside.txt", "content")


def test_delete_requires_explicit_confirmation(files, tmp_path):
    target = tmp_path / "a.txt"
    target.write_text("content")
    with pytest.raises(PermissionConfirmationRequired):
        files.delete_path(target)
    assert target.exists()
    files.delete_path(target, confirmed=True)
    assert not target.exists()


def test_registry_exposes_exact_file_tools(files):
    registry = file_tool_registry(files)
    assert set(registry) == {"list_files", "read_file", "write_file", "delete_path"}
    for tool in registry.values():
        parameters = tool.model_schema()["function"]["parameters"]
        assert parameters["required"]
