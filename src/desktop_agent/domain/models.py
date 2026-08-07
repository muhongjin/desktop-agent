from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class SessionStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class MessageStatus(StrEnum):
    COMPLETE = "complete"
    STOPPED = "stopped"


class ToolRunStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class Session:
    id: str
    title: str
    workspace_path: str
    associated_directory: str | None
    current_model_id: str | None
    thinking_strength: str | None
    execution_mode: str
    status: SessionStatus
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class Message:
    id: str
    session_id: str
    role: MessageRole
    content: str
    model_id: str | None
    thinking_strength: str | None
    request_params: dict[str, Any]
    tool_calls: tuple[dict[str, Any], ...]
    tool_call_id: str | None
    status: MessageStatus
    completion_marker: bool
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ToolRun:
    id: str
    session_id: str
    tool_name: str
    input_json: str
    raw_output: str
    status: ToolRunStatus
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    provider_id: str
    display_name: str
    base_url: str
    config: dict[str, Any]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class AppSetting:
    key: str
    value: Any
    updated_at: datetime
