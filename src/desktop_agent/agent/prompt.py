import json
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

from desktop_agent.domain.models import Message, MessageRole


@dataclass(frozen=True, slots=True)
class PromptRequest:
    kernel: str
    global_prompt: str
    messages: tuple[dict[str, Any], ...]
    tools: tuple[dict[str, Any], ...]


class PromptComposer:
    def __init__(self, global_prompt: str = "", recent_limit: int = 50):
        self.global_prompt = global_prompt
        self.recent_limit = recent_limit

    def compose(
        self,
        history: list[Message],
        *,
        workspace: str | Path,
        associated_directory: str | Path | None = None,
        tools: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
    ) -> PromptRequest:
        kernel = files("desktop_agent.resources").joinpath("kernel.md").read_text(encoding="utf-8").strip()
        messages: list[dict[str, Any]] = [{"role": "system", "content": kernel}]
        if self.global_prompt.strip():
            messages.append({"role": "system", "content": self.global_prompt.strip()})
        usable = [message for message in history if message.completion_marker]
        messages.extend(self._message_payload(message) for message in usable[-self.recent_limit :])
        workspace_context = {"workspace": str(Path(workspace).resolve())}
        if associated_directory is not None:
            workspace_context["associated_directory"] = str(Path(associated_directory).resolve())
        messages.append(
            {
                "role": "system",
                "content": "Current workspace metadata: "
                + json.dumps(workspace_context, ensure_ascii=False, separators=(",", ":")),
            }
        )
        return PromptRequest(kernel, self.global_prompt.strip(), tuple(messages), tuple(tools))

    def _message_payload(self, message: Message) -> dict[str, Any]:
        payload: dict[str, Any] = {"role": message.role.value, "content": message.content}
        if message.role is MessageRole.ASSISTANT and message.tool_calls:
            payload["tool_calls"] = list(message.tool_calls)
        if message.role is MessageRole.TOOL and message.tool_call_id:
            payload["tool_call_id"] = message.tool_call_id
        return payload
