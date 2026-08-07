from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from desktop_agent.tools.base import ToolResult
from desktop_agent.tools.files import FileTools


@dataclass(frozen=True, slots=True)
class RegisteredTool:
    name: str
    description: str
    input_schema: dict[str, Any]
    callable: Callable[..., ToolResult]
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
