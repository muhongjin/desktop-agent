import asyncio
import inspect
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import suppress
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from desktop_agent.domain.models import MessageRole, MessageStatus, ToolRunStatus
from desktop_agent.providers.openai_compatible import (
    AssistantTurn,
    OpenAICompatibleClient,
    ProviderError,
    TextDelta,
    ToolCall,
)
from desktop_agent.security.permissions import (
    PermissionBroker,
    PermissionDecision,
    PermissionRequest,
    SessionAccess,
)
from desktop_agent.tools.base import ToolResult
from desktop_agent.tools.registry import RegisteredTool


class TurnStopped(Exception):
    pass


@dataclass(frozen=True, slots=True)
class AgentEvent:
    type: str
    data: dict[str, Any]


PermissionHandler = Callable[
    [PermissionRequest, RegisteredTool, dict[str, Any]], Awaitable[bool] | bool
]


class AgentLoop:
    def __init__(
        self,
        repository,
        prompt_composer,
        provider: OpenAICompatibleClient,
        permission_broker: PermissionBroker,
        tool_registry: dict[str, RegisteredTool],
        permission_handler: PermissionHandler | None = None,
    ):
        self.repository = repository
        self.prompt_composer = prompt_composer
        self.provider = provider
        self.permission_broker = permission_broker
        self.tool_registry = tool_registry
        self.permission_handler = permission_handler

    async def send_message(
        self,
        session_id: str,
        content: str,
        *,
        model_id: str,
        thinking_strength: str | None,
        access: SessionAccess,
        request_params: dict[str, Any] | None = None,
        stop_event: asyncio.Event | None = None,
    ) -> AsyncIterator[AgentEvent]:
        self.repository.append_message(
            session_id,
            MessageRole.USER,
            content,
            model_id=model_id,
            thinking_strength=thinking_strength,
            request_params=request_params,
        )
        while True:
            draft = self.repository.append_message(
                session_id,
                MessageRole.ASSISTANT,
                "",
                model_id=model_id,
                thinking_strength=thinking_strength,
                request_params=request_params,
                status=MessageStatus.STOPPED,
                completion_marker=False,
            )
            session = self.repository.get_session(session_id)
            history = [
                message
                for message in self.repository.list_messages(session_id)
                if message.id != draft.id
            ]
            enabled_tools = [
                tool
                for tool in self.tool_registry.values()
                if self.permission_broker.evaluate(
                    PermissionRequest(tool.capability, access.workspace.resolve(strict=False)),
                    access,
                )
                is not PermissionDecision.DENY
            ]
            schemas = [tool.model_schema() for tool in enabled_tools]
            prompt = self.prompt_composer.compose(
                history,
                workspace=session.workspace_path,
                associated_directory=session.associated_directory,
                tools=schemas,
            )
            accumulated = ""
            final_turn = None
            try:
                stream = self.provider.stream_chat(
                    model_id=model_id,
                    messages=prompt.messages,
                    thinking_strength=thinking_strength,
                    tools=prompt.tools,
                    request_params=request_params,
                )
                async for event in self._stream_until_stopped(stream, stop_event):
                    if isinstance(event, TextDelta):
                        accumulated += event.text
                        self.repository.update_message(
                            draft.id, accumulated, MessageStatus.STOPPED, completion_marker=False
                        )
                        yield AgentEvent("text_delta", {"message_id": draft.id, "text": event.text})
                    elif isinstance(event, AssistantTurn):
                        final_turn = event
            except TurnStopped:
                self.repository.update_message(
                    draft.id, accumulated, MessageStatus.STOPPED, completion_marker=True
                )
                yield AgentEvent("turn_stopped", {"message_id": draft.id})
                return
            except ProviderError as error:
                visible_error = (
                    f"{accumulated}\n\n错误：{error}" if accumulated else f"错误：{error}"
                )
                self.repository.update_message(
                    draft.id, visible_error, MessageStatus.STOPPED, completion_marker=True
                )
                yield AgentEvent("turn_stopped", {"message_id": draft.id, "error": str(error)})
                return

            if final_turn is None:
                self.repository.update_message(
                    draft.id, accumulated, MessageStatus.STOPPED, completion_marker=True
                )
                yield AgentEvent(
                    "turn_stopped",
                    {"message_id": draft.id, "error": "Provider stream ended unexpectedly"},
                )
                return

            if not final_turn.tool_calls:
                completed = self.repository.update_message(
                    draft.id, accumulated, MessageStatus.COMPLETE, completion_marker=True
                )
                yield AgentEvent("turn_finished", {"message_id": completed.id})
                return

            tool_payloads = [self._tool_call_payload(call) for call in final_turn.tool_calls]
            self.repository.update_message(
                draft.id,
                accumulated,
                MessageStatus.COMPLETE,
                completion_marker=True,
                tool_calls=tool_payloads,
            )
            for call in final_turn.tool_calls:
                async for event in self._execute_tool(session_id, call, access, stop_event):
                    yield event
                    if event.type == "turn_stopped":
                        return

    async def _execute_tool(
        self,
        session_id: str,
        call: ToolCall,
        access: SessionAccess,
        stop_event: asyncio.Event | None,
    ) -> AsyncIterator[AgentEvent]:
        tool = self.tool_registry.get(call.name)
        try:
            arguments = json.loads(call.arguments or "{}")
        except json.JSONDecodeError as error:
            async for event in self._record_tool_failure(
                session_id, call, {}, f"Invalid tool arguments: {error}"
            ):
                yield event
            return
        if not isinstance(arguments, dict):
            async for event in self._record_tool_failure(
                session_id, call, {}, "Tool arguments must be a JSON object"
            ):
                yield event
            return
        if tool is None:
            async for event in self._record_tool_failure(
                session_id, call, arguments, f"Unknown tool: {call.name}"
            ):
                yield event
            return
        target = Path(arguments.get(tool.path_argument, access.workspace)).expanduser()
        if not target.is_absolute():
            target = access.workspace / target
        request = PermissionRequest(tool.capability, target.resolve(strict=False))
        decision = self.permission_broker.evaluate(request, access)
        confirmed = False
        if decision is PermissionDecision.CONFIRM:
            yield AgentEvent(
                "permission_required",
                {"tool_call_id": call.id, "tool": tool.name, "path": str(request.path)},
            )
            if stop_event is not None and stop_event.is_set():
                yield AgentEvent("turn_stopped", {"tool_call_id": call.id})
                return
            if self.permission_handler is not None:
                answer = self.permission_handler(request, tool, arguments)
                confirmed = bool(await answer) if inspect.isawaitable(answer) else bool(answer)
            if stop_event is not None and stop_event.is_set():
                yield AgentEvent("turn_stopped", {"tool_call_id": call.id})
                return
            if not confirmed:
                async for event in self._record_tool_failure(
                    session_id, call, arguments, "Permission denied"
                ):
                    yield event
                return
        elif decision is PermissionDecision.DENY:
            async for event in self._record_tool_failure(
                session_id, call, arguments, "Permission denied"
            ):
                yield event
            return

        yield AgentEvent("tool_started", {"tool_call_id": call.id, "tool": tool.name})
        try:
            invoke_arguments = dict(arguments)
            if confirmed and "confirmed" in inspect.signature(tool.callable).parameters:
                invoke_arguments["confirmed"] = True
            if (
                stop_event is not None
                and "stop_event" in inspect.signature(tool.callable).parameters
            ):
                invoke_arguments["stop_event"] = stop_event
            result = tool.callable(**invoke_arguments)
            result = await result if inspect.isawaitable(result) else result
            normalized, raw = self._normalize_result(result)
            status = (
                ToolRunStatus.CANCELLED
                if getattr(result, "cancelled", False)
                else ToolRunStatus.COMPLETED
            )
        except (OSError, TypeError, ValueError, RuntimeError) as error:
            normalized, raw, status = f"Tool failed: {error}", str(error), ToolRunStatus.FAILED
        self.repository.append_tool_run(session_id, tool.name, arguments, raw, status)
        self.repository.append_message(
            session_id,
            MessageRole.TOOL,
            normalized,
            tool_call_id=call.id,
        )
        yield AgentEvent(
            "tool_finished",
            {
                "tool_call_id": call.id,
                "tool": tool.name,
                "status": status.value,
                "output": normalized,
            },
        )
        if status is ToolRunStatus.CANCELLED:
            yield AgentEvent("turn_stopped", {"tool_call_id": call.id})

    async def _record_tool_failure(
        self, session_id: str, call: ToolCall, arguments: dict[str, Any], error: str
    ) -> AsyncIterator[AgentEvent]:
        self.repository.append_tool_run(
            session_id, call.name, arguments, error, ToolRunStatus.FAILED
        )
        self.repository.append_message(session_id, MessageRole.TOOL, error, tool_call_id=call.id)
        yield AgentEvent(
            "tool_finished",
            {
                "tool_call_id": call.id,
                "tool": call.name,
                "status": ToolRunStatus.FAILED.value,
                "output": error,
            },
        )

    async def _stream_until_stopped(self, stream, stop_event: asyncio.Event | None):
        iterator = stream.__aiter__()
        while True:
            next_event = asyncio.create_task(iterator.__anext__())
            stop_waiter = asyncio.create_task(stop_event.wait()) if stop_event is not None else None
            try:
                if stop_waiter is None:
                    yield await next_event
                    continue
                done, _ = await asyncio.wait(
                    {next_event, stop_waiter}, return_when=asyncio.FIRST_COMPLETED
                )
                if stop_waiter in done and stop_event.is_set():
                    if not next_event.done():
                        next_event.cancel()
                        with suppress(asyncio.CancelledError):
                            await next_event
                    with suppress(asyncio.CancelledError, RuntimeError):
                        await iterator.aclose()
                    raise TurnStopped
                yield next_event.result()
            except StopAsyncIteration:
                return
            finally:
                if stop_waiter is not None:
                    stop_waiter.cancel()

    def _tool_call_payload(self, call: ToolCall) -> dict[str, Any]:
        return {
            "id": call.id,
            "type": "function",
            "function": {"name": call.name, "arguments": call.arguments},
        }

    def _normalize_result(self, result: Any) -> tuple[str, str]:
        if isinstance(result, ToolResult):
            payload = asdict(result)
            raw = json.dumps(payload, ensure_ascii=False, default=str)
            return result.diff_summary if result.data is None else str(result.data), raw
        if hasattr(result, "stdout") and hasattr(result, "stderr"):
            payload = asdict(result)
            raw = json.dumps(payload, ensure_ascii=False, default=str)
            normalized = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
            return normalized or f"Process exited with code {result.exit_code}", raw
        if isinstance(result, str):
            return result, result
        raw = json.dumps(result, ensure_ascii=False, default=str)
        return raw, raw
