import json
import math
import re
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
    estimated_tokens: int = 0
    truncated: bool = False


class PromptComposer:
    DEFAULT_CONTEXT_LIMIT = 128_000
    INPUT_BUDGET_RATIO = 0.82

    def __init__(self, global_prompt: str = ""):
        self.global_prompt = global_prompt

    def compose(
        self,
        history: list[Message],
        *,
        workspace: str | Path,
        associated_directory: str | Path | None = None,
        tools: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
        context_limit: int | None = None,
        truncate: bool = False,
        force_truncate: bool = False,
    ) -> PromptRequest:
        kernel = (
            files("desktop_agent.resources")
            .joinpath("kernel.md")
            .read_text(encoding="utf-8")
            .strip()
        )
        messages: list[dict[str, Any]] = [{"role": "system", "content": kernel}]
        if self.global_prompt.strip():
            messages.append({"role": "system", "content": self.global_prompt.strip()})
        usable = [message for message in history if message.completion_marker]
        history_groups = self._history_groups(usable)
        history_payload = [
            self._message_payload(message) for group in history_groups for message in group
        ]
        workspace_context = {"workspace": str(Path(workspace).resolve())}
        if associated_directory is not None:
            workspace_context["associated_directory"] = str(Path(associated_directory).resolve())
        workspace_message = {
            "role": "system",
            "content": "Current workspace metadata: "
            + json.dumps(workspace_context, ensure_ascii=False, separators=(",", ":")),
        }
        if truncate:
            limit = self._context_limit(context_limit)
            budget = max(1, math.floor(limit * self.INPUT_BUDGET_RATIO))
            history_payload, was_truncated = self._truncate_history(
                messages,
                history_groups,
                workspace_message,
                tools,
                budget,
                force_truncate=force_truncate,
            )
            messages.extend(history_payload)
            messages.append(workspace_message)
        else:
            messages.extend(history_payload)
            messages.append(workspace_message)
            was_truncated = False
        estimated_tokens = self.estimate_tokens(messages, tools)
        return PromptRequest(
            kernel,
            self.global_prompt.strip(),
            tuple(messages),
            tuple(tools),
            estimated_tokens,
            was_truncated,
        )

    @classmethod
    def _context_limit(cls, value: int | None) -> int:
        try:
            parsed = int(value or 0)
        except (TypeError, ValueError):
            parsed = 0
        return parsed if parsed > 0 else cls.DEFAULT_CONTEXT_LIMIT

    @staticmethod
    def _history_groups(history: list[Message]) -> list[list[Message]]:
        groups: list[list[Message]] = []
        current: list[Message] = []
        for message in history:
            if current and message.role is MessageRole.USER:
                groups.append(current)
                current = []
            current.append(message)
        if current:
            groups.append(current)
        return groups

    def _truncate_history(
        self,
        prefix: list[dict[str, Any]],
        groups: list[list[Message]],
        workspace_message: dict[str, Any],
        tools: list[dict[str, Any]] | tuple[dict[str, Any], ...],
        budget: int,
        *,
        force_truncate: bool,
    ) -> tuple[list[dict[str, Any]], bool]:
        selected = list(groups)
        was_truncated = False

        def payload() -> list[dict[str, Any]]:
            return [self._message_payload(message) for group in selected for message in group]

        if force_truncate and len(selected) > 1:
            selected.pop(0)
            was_truncated = True
        while selected and self.estimate_tokens(prefix + payload() + [workspace_message], tools) > budget:
            if len(selected) == 1:
                break
            selected.pop(0)
            was_truncated = True
        return payload(), was_truncated

    @staticmethod
    def estimate_tokens(
        messages: list[dict[str, Any]] | tuple[dict[str, Any], ...],
        tools: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
    ) -> int:
        serialized = json.dumps(
            {"messages": list(messages), "tools": list(tools)},
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
        cjk = len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", serialized))
        other = len(serialized) - cjk
        return max(1, cjk + math.ceil(other / 4))

    def _message_payload(self, message: Message) -> dict[str, Any]:
        payload: dict[str, Any] = {"role": message.role.value, "content": message.content}
        if message.role is MessageRole.ASSISTANT and message.tool_calls:
            payload["tool_calls"] = list(message.tool_calls)
        if message.role is MessageRole.TOOL and message.tool_call_id:
            payload["tool_call_id"] = message.tool_call_id
        return payload
