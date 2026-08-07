from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from desktop_agent.tools.files import FileTools


@dataclass(frozen=True, slots=True)
class RegisteredTool:
    name: str
    description: str
    input_schema: dict[str, Any]
    callable: Callable[..., Any]
    capability: str
    path_argument: str = "path"

    def model_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {"name": self.name, "description": self.description, "parameters": self.input_schema},
        }


def file_tool_registry(files: FileTools) -> dict[str, RegisteredTool]:
    path_schema = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
        "additionalProperties": False,
    }
    return {
        "list_files": RegisteredTool("list_files", "List directory entries", path_schema, files.list_files, "fs.read"),
        "read_file": RegisteredTool("read_file", "Read a text file", path_schema, files.read_file, "fs.read"),
        "write_file": RegisteredTool(
            "write_file",
            "Write a text file atomically",
            {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
                "additionalProperties": False,
            },
            files.write_file,
            "fs.write",
        ),
        "delete_path": RegisteredTool(
            "delete_path", "Delete a file or empty directory", path_schema, files.delete_path, "fs.delete"
        ),
    }


def powershell_tool(executor, workspace) -> RegisteredTool:
    async def run(command: str, cwd: str | None = None, stop_event=None):
        working_directory = Path(cwd) if cwd else Path(workspace)
        if not working_directory.is_absolute():
            working_directory = Path(workspace) / working_directory
        return await executor.execute(command, cwd=working_directory.resolve(), stop_event=stop_event)

    return RegisteredTool(
        "run_powershell",
        "Run a PowerShell command in the session workspace",
        {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "cwd": {"type": "string"},
            },
            "required": ["command"],
            "additionalProperties": False,
        },
        run,
        "process.exec",
        "cwd",
    )
