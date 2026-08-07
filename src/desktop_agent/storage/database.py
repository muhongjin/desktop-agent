import sqlite3
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    workspace_path TEXT NOT NULL,
    associated_directory TEXT,
    current_model_id TEXT,
    thinking_strength TEXT,
    execution_mode TEXT NOT NULL DEFAULT 'local' CHECK (execution_mode IN ('none', 'local')),
    status TEXT NOT NULL CHECK (status IN ('active', 'archived')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'tool')),
    content TEXT NOT NULL,
    model_id TEXT,
    thinking_strength TEXT,
    request_params TEXT NOT NULL DEFAULT '{}',
    tool_calls_json TEXT NOT NULL DEFAULT '[]',
    tool_call_id TEXT,
    status TEXT NOT NULL CHECK (status IN ('complete', 'stopped')),
    completion_marker INTEGER NOT NULL CHECK (completion_marker IN (0, 1)),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tool_runs (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    tool_name TEXT NOT NULL,
    input_json TEXT NOT NULL,
    raw_output TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('completed', 'failed', 'cancelled')),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS provider_configs (
    provider_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    base_url TEXT NOT NULL,
    config_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.execute("PRAGMA busy_timeout = 5000")
        self.connection.executescript(SCHEMA)
        columns = {row["name"] for row in self.connection.execute("PRAGMA table_info(sessions)")}
        if "associated_directory" not in columns:
            self.connection.execute("ALTER TABLE sessions ADD COLUMN associated_directory TEXT")
        if "current_model_id" not in columns:
            self.connection.execute("ALTER TABLE sessions ADD COLUMN current_model_id TEXT")
        if "thinking_strength" not in columns:
            self.connection.execute("ALTER TABLE sessions ADD COLUMN thinking_strength TEXT")
        if "execution_mode" not in columns:
            self.connection.execute(
                "ALTER TABLE sessions ADD COLUMN execution_mode TEXT NOT NULL DEFAULT 'local'"
            )
        message_columns = {
            row["name"] for row in self.connection.execute("PRAGMA table_info(messages)")
        }
        if "tool_calls_json" not in message_columns:
            self.connection.execute(
                "ALTER TABLE messages ADD COLUMN tool_calls_json TEXT NOT NULL DEFAULT '[]'"
            )
        if "tool_call_id" not in message_columns:
            self.connection.execute("ALTER TABLE messages ADD COLUMN tool_call_id TEXT")
        self.connection.commit()

    def execute(self, sql: str, parameters: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        return self.connection.execute(sql, parameters)

    def transaction(self):
        return self.connection

    def close(self) -> None:
        self.connection.close()
