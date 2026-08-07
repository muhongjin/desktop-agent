import json
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from desktop_agent.domain.models import (
    AppSetting,
    Message,
    MessageRole,
    MessageStatus,
    ProviderConfig,
    Session,
    SessionStatus,
    ToolRun,
    ToolRunStatus,
)
from desktop_agent.storage.database import Database


class RepositoryError(Exception):
    """Base class for persistence errors."""


class InvalidSessionState(RepositoryError):
    pass


_SECRET_KEY = re.compile(r"(?:key|token|secret|password|passwd|authorization|cookie)", re.IGNORECASE)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _id() -> str:
    return str(uuid.uuid4())


def _safe_params(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe_params(item) for key, item in value.items() if not _SECRET_KEY.search(str(key))}
    if isinstance(value, list):
        return [_safe_params(item) for item in value]
    if isinstance(value, tuple):
        return [_safe_params(item) for item in value]
    return value


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


class Repository:
    def __init__(self, database: Database):
        self.database = database

    def create_session(
        self,
        title: str,
        workspace_path: str,
        current_model_id: str | None = None,
        thinking_strength: str | None = None,
        execution_mode: str = "local",
        session_id: str | None = None,
    ) -> Session:
        session_id, now = session_id or _id(), _now()
        with self.database.transaction():
            self.database.execute(
                "INSERT INTO sessions (id, title, workspace_path, associated_directory, current_model_id, "
                "thinking_strength, execution_mode, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    title,
                    workspace_path,
                    None,
                    current_model_id,
                    thinking_strength,
                    execution_mode,
                    SessionStatus.ACTIVE,
                    now,
                    now,
                ),
            )
        return self.get_session(session_id)

    def get_session(self, session_id: str) -> Session | None:
        row = self.database.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            return None
        return Session(
            id=row["id"],
            title=row["title"],
            workspace_path=row["workspace_path"],
            associated_directory=row["associated_directory"],
            current_model_id=row["current_model_id"],
            thinking_strength=row["thinking_strength"],
            execution_mode=row["execution_mode"],
            status=SessionStatus(row["status"]),
            created_at=_timestamp(row["created_at"]),
            updated_at=_timestamp(row["updated_at"]),
        )

    def list_sessions(self, status: SessionStatus | None = None) -> list[Session]:
        if status is None:
            rows = self.database.execute("SELECT id FROM sessions ORDER BY updated_at DESC, rowid DESC").fetchall()
        else:
            rows = self.database.execute(
                "SELECT id FROM sessions WHERE status = ? ORDER BY updated_at DESC, rowid DESC", (status,)
            ).fetchall()
        return [self.get_session(row["id"]) for row in rows]

    def _set_session_status(self, session_id: str, expected: SessionStatus, target: SessionStatus) -> Session:
        now = _now()
        with self.database.transaction():
            cursor = self.database.execute(
                "UPDATE sessions SET status = ?, updated_at = ? WHERE id = ? AND status = ?",
                (target, now, session_id, expected),
            )
            if cursor.rowcount == 0:
                if self.get_session(session_id) is None:
                    raise KeyError(f"Unknown session: {session_id}")
                raise InvalidSessionState(f"Session must be {expected.value}")
        return self.get_session(session_id)

    def set_associated_directory(self, session_id: str, path: str | None) -> Session:
        with self.database.transaction():
            self._require_session(session_id)
            self.database.execute(
                "UPDATE sessions SET associated_directory = ?, updated_at = ? WHERE id = ?",
                (path, _now(), session_id),
            )
        return self.get_session(session_id)

    def update_session_preferences(
        self,
        session_id: str,
        *,
        model_id: str | None = None,
        thinking_strength: str | None = None,
        execution_mode: str | None = None,
    ) -> Session:
        session = self.get_session(session_id)
        if session is None:
            raise KeyError(f"Unknown session: {session_id}")
        values = (
            session.current_model_id if model_id is None else model_id,
            session.thinking_strength if thinking_strength is None else thinking_strength,
            session.execution_mode if execution_mode is None else execution_mode,
            _now(),
            session_id,
        )
        with self.database.transaction():
            self.database.execute(
                "UPDATE sessions SET current_model_id = ?, thinking_strength = ?, execution_mode = ?, "
                "updated_at = ? WHERE id = ?",
                values,
            )
        return self.get_session(session_id)

    def archive_session(self, session_id: str) -> Session:
        return self._set_session_status(session_id, SessionStatus.ACTIVE, SessionStatus.ARCHIVED)

    def restore_session(self, session_id: str) -> Session:
        return self._set_session_status(session_id, SessionStatus.ARCHIVED, SessionStatus.ACTIVE)

    def delete_session(self, session_id: str) -> None:
        with self.database.transaction():
            session = self.get_session(session_id)
            if session is None:
                raise KeyError(f"Unknown session: {session_id}")
            if session.status is not SessionStatus.ARCHIVED:
                raise InvalidSessionState("Only archived sessions can be deleted")
            self.database.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    def append_message(
        self,
        session_id: str,
        role: MessageRole,
        content: Any,
        model_id: str | None = None,
        thinking_strength: str | None = None,
        request_params: dict[str, Any] | None = None,
        tool_calls: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
        tool_call_id: str | None = None,
        status: MessageStatus = MessageStatus.COMPLETE,
        completion_marker: bool = True,
    ) -> Message:
        message_id, now = _id(), _now()
        normalized_content = content if isinstance(content, str) else _json(content)
        safe_request_params = _safe_params(request_params or {})
        with self.database.transaction():
            self._require_session(session_id)
            self.database.execute(
                "INSERT INTO messages (id, session_id, role, content, model_id, thinking_strength, "
                "request_params, tool_calls_json, tool_call_id, status, completion_marker, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    message_id,
                    session_id,
                    role,
                    normalized_content,
                    model_id,
                    thinking_strength,
                    _json(safe_request_params),
                    _json(tool_calls or []),
                    tool_call_id,
                    status,
                    int(completion_marker),
                    now,
                ),
            )
        return self._get_message(message_id)

    def update_message(
        self,
        message_id: str,
        content: Any,
        status: MessageStatus,
        completion_marker: bool,
        tool_calls: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    ) -> Message:
        normalized_content = content if isinstance(content, str) else _json(content)
        with self.database.transaction():
            cursor = self.database.execute(
                "UPDATE messages SET content = ?, status = ?, completion_marker = ?, "
                "tool_calls_json = COALESCE(?, tool_calls_json) WHERE id = ?",
                (
                    normalized_content,
                    status,
                    int(completion_marker),
                    _json(tool_calls) if tool_calls is not None else None,
                    message_id,
                ),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Unknown message: {message_id}")
        return self._get_message(message_id)

    def _require_session(self, session_id: str) -> None:
        if self.get_session(session_id) is None:
            raise KeyError(f"Unknown session: {session_id}")

    def _get_message(self, message_id: str) -> Message:
        row = self.database.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        if row is None:
            raise KeyError(f"Unknown message: {message_id}")
        return Message(
            id=row["id"],
            session_id=row["session_id"],
            role=MessageRole(row["role"]),
            content=row["content"],
            model_id=row["model_id"],
            thinking_strength=row["thinking_strength"],
            request_params=json.loads(row["request_params"]),
            tool_calls=tuple(json.loads(row["tool_calls_json"])),
            tool_call_id=row["tool_call_id"],
            status=MessageStatus(row["status"]),
            completion_marker=bool(row["completion_marker"]),
            created_at=_timestamp(row["created_at"]),
        )

    def list_messages(self, session_id: str) -> list[Message]:
        rows = self.database.execute(
            "SELECT id FROM messages WHERE session_id = ? ORDER BY created_at, rowid", (session_id,)
        ).fetchall()
        return [self._get_message(row["id"]) for row in rows]

    def append_tool_run(
        self,
        session_id: str,
        tool_name: str,
        input_json: Any,
        raw_output: str,
        status: ToolRunStatus,
    ) -> ToolRun:
        run_id, now = _id(), _now()
        normalized_input = input_json if isinstance(input_json, str) else _json(input_json)
        with self.database.transaction():
            self._require_session(session_id)
            self.database.execute(
                "INSERT INTO tool_runs (id, session_id, tool_name, input_json, raw_output, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (run_id, session_id, tool_name, normalized_input, raw_output, status, now),
            )
        return self._get_tool_run(run_id)

    def _get_tool_run(self, run_id: str) -> ToolRun:
        row = self.database.execute("SELECT * FROM tool_runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(f"Unknown tool run: {run_id}")
        return ToolRun(
            id=row["id"],
            session_id=row["session_id"],
            tool_name=row["tool_name"],
            input_json=row["input_json"],
            raw_output=row["raw_output"],
            status=ToolRunStatus(row["status"]),
            created_at=_timestamp(row["created_at"]),
        )

    def list_tool_runs(self, session_id: str) -> list[ToolRun]:
        rows = self.database.execute(
            "SELECT id FROM tool_runs WHERE session_id = ? ORDER BY created_at, rowid", (session_id,)
        ).fetchall()
        return [self._get_tool_run(row["id"]) for row in rows]

    def set_provider_config(self, config: ProviderConfig) -> None:
        with self.database.transaction():
            self.database.execute(
                "INSERT INTO provider_configs (provider_id, display_name, base_url, config_json, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(provider_id) DO UPDATE SET display_name=excluded.display_name, "
                "base_url=excluded.base_url, config_json=excluded.config_json, updated_at=excluded.updated_at",
                (
                    config.provider_id,
                    config.display_name,
                    config.base_url,
                    _json(_safe_params(config.config)),
                    config.created_at.isoformat(),
                    config.updated_at.isoformat(),
                ),
            )

    def get_provider_config(self, provider_id: str) -> ProviderConfig | None:
        row = self.database.execute(
            "SELECT * FROM provider_configs WHERE provider_id = ?", (provider_id,)
        ).fetchone()
        if row is None:
            return None
        return ProviderConfig(
            provider_id=row["provider_id"],
            display_name=row["display_name"],
            base_url=row["base_url"],
            config=json.loads(row["config_json"]),
            created_at=_timestamp(row["created_at"]),
            updated_at=_timestamp(row["updated_at"]),
        )

    def list_provider_configs(self) -> list[ProviderConfig]:
        rows = self.database.execute("SELECT provider_id FROM provider_configs ORDER BY display_name").fetchall()
        return [self.get_provider_config(row["provider_id"]) for row in rows]

    def set_app_setting(self, key: str, value: Any) -> None:
        with self.database.transaction():
            self.database.execute(
                "INSERT INTO app_settings (key, value_json, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at",
                (key, _json(value), _now()),
            )

    def get_app_setting(self, key: str) -> AppSetting | None:
        row = self.database.execute("SELECT * FROM app_settings WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        return AppSetting(key=row["key"], value=json.loads(row["value_json"]), updated_at=_timestamp(row["updated_at"]))
