import os
import tempfile
from pathlib import Path

from desktop_agent.security.permissions import (
    PermissionBroker,
    PermissionDecision,
    PermissionRequest,
    SessionAccess,
)
from desktop_agent.tools.base import ToolResult


class PermissionDenied(Exception):
    pass


class PermissionConfirmationRequired(Exception):
    pass


class FileTools:
    def __init__(self, broker: PermissionBroker, access: SessionAccess):
        self.broker = broker
        self.access = access

    def list_files(self, path: str | Path) -> ToolResult:
        target = self._authorize("fs.read", path)
        entries = [item.name for item in sorted(target.iterdir(), key=lambda item: item.name.casefold())]
        return ToolResult(str(target), 0, f"listed {len(entries)} entries", entries)

    def read_file(self, path: str | Path, encoding: str = "utf-8") -> ToolResult:
        target = self._authorize("fs.read", path)
        content = target.read_text(encoding=encoding)
        return ToolResult(str(target), len(content.encode(encoding)), "read file", content)

    def write_file(self, path: str | Path, content: str, encoding: str = "utf-8") -> ToolResult:
        target = self._authorize("fs.write", path)
        target.parent.mkdir(parents=True, exist_ok=True)
        existed = target.exists()
        previous_size = target.stat().st_size if existed else 0
        handle, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(handle, "w", encoding=encoding, newline="") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        byte_count = len(content.encode(encoding))
        action = "updated" if existed else "created"
        return ToolResult(str(target), byte_count, f"{action} file ({previous_size} -> {byte_count} bytes)")

    def delete_path(self, path: str | Path, *, confirmed: bool = False) -> ToolResult:
        target = self._authorize("fs.delete", path, confirmed=confirmed)
        byte_count = target.stat().st_size if target.is_file() else 0
        if target.is_dir():
            target.rmdir()
        else:
            target.unlink()
        return ToolResult(str(target), byte_count, "deleted path")

    def _authorize(
        self, capability: str, path: str | Path, *, risk: str | None = None, confirmed: bool = False
    ) -> Path:
        target = Path(path).expanduser()
        if not target.is_absolute():
            target = self.access.workspace / target
        target = target.resolve(strict=False)
        decision = self.broker.evaluate(PermissionRequest(capability, target, risk), self.access)
        if decision is PermissionDecision.DENY:
            raise PermissionDenied(f"{capability} is not allowed for {target}")
        if decision is PermissionDecision.CONFIRM and not confirmed:
            raise PermissionConfirmationRequired(f"{capability} requires confirmation for {target}")
        return target
