from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class ToolResult:
    path: str
    byte_count: int
    diff_summary: str
    data: Any = None


class Tool(Protocol):
    name: str
    description: str
    input_schema: dict[str, Any]

    def __call__(self, **arguments: Any) -> ToolResult: ...
