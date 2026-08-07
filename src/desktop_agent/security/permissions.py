from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import ClassVar


class PermissionDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    CONFIRM = "confirm"


class AccessMode(StrEnum):
    NONE = "none"
    LOCAL = "local"
    FULL = "full"


@dataclass(frozen=True, slots=True)
class PermissionRequest:
    capability: str
    path: Path
    risk: str | None = None


@dataclass(frozen=True, slots=True)
class SessionAccess:
    mode: AccessMode
    workspace: Path
    associated_directory: Path | None = None

    @classmethod
    def none(cls, workspace: Path, associated_directory: Path | None = None):
        return cls(AccessMode.NONE, workspace, associated_directory)

    @classmethod
    def local(cls, workspace: Path, associated_directory: Path | None = None):
        return cls(AccessMode.LOCAL, workspace, associated_directory)

    @classmethod
    def full_access(cls, workspace: Path, associated_directory: Path | None = None):
        return cls(AccessMode.FULL, workspace, associated_directory)


class PermissionBroker:
    high_risks: ClassVar[frozenset[str]] = frozenset(
        {"privilege-escalation", "system-change", "high-risk-delete"}
    )

    def evaluate(self, request: PermissionRequest, access: SessionAccess) -> PermissionDecision:
        capability = request.capability
        path = request.path.expanduser().resolve(strict=False)
        trusted = self._is_trusted(path, access)

        if access.mode is AccessMode.NONE:
            if capability == "fs.read" and trusted:
                return PermissionDecision.ALLOW
            return PermissionDecision.DENY

        if access.mode is AccessMode.LOCAL and not trusted:
            return PermissionDecision.DENY

        if request.risk in self.high_risks:
            return PermissionDecision.CONFIRM

        if capability == "fs.delete":
            return PermissionDecision.CONFIRM
        if capability in {"fs.read", "fs.write", "process.exec"}:
            return PermissionDecision.ALLOW
        return PermissionDecision.DENY

    def _is_trusted(self, path: Path, access: SessionAccess) -> bool:
        roots = [access.workspace]
        if access.associated_directory is not None:
            roots.append(access.associated_directory)
        return any(path.is_relative_to(root.expanduser().resolve(strict=False)) for root in roots)
