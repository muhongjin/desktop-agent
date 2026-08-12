import asyncio
import inspect
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import suppress
from dataclasses import asdict
from pathlib import Path
from typing import Any

from desktop_agent.domain.models import MessageRole, MessageStatus, ToolRunStatus
from desktop_agent.providers.openai_compatible import (
    OpenAICompatibleClient,
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

from .session_processor import AgentEvent, SessionProcessor
from .session_retry import SessionRetry

PermissionHandler = Callable[
    [PermissionRequest, RegisteredTool, dict[str, Any]], Awaitable[bool] | bool
]


class ToolStopped(Exception):
    pass


class AgentLoop:
    def __init__(
        self,
        repository,
        prompt_composer,
        provider: OpenAICompatibleClient,
        permission_broker: PermissionBroker,
        tool_registry: dict[str, RegisteredTool],
        permission_handler: PermissionHandler | None = None,
        context_limit: int | None = None,
        session_retry: SessionRetry | None = None,
    ):
        self.repository = repository
        self.prompt_composer = prompt_composer
        self.permission_broker = permission_broker
        self.tool_registry = tool_registry
        self.permission_handler = permission_handler
        self.context_limit = context_limit
        self.session_processor = SessionProcessor(repository, provider, session_retry)

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
        initial_messages=None,
    ) -> AsyncIterator[AgentEvent]:
        if initial_messages is None:
            user_message = self.repository.append_message(
                session_id,
                MessageRole.USER,
                content,
                model_id=model_id,
                thinking_strength=thinking_strength,
                request_params=request_params,
            )
            initial_draft = None
        else:
            user_message, initial_draft = initial_messages
        first_turn = True
        while True:
            is_initial_turn = first_turn
            draft = initial_draft if first_turn else None
            if draft is None:
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
            yield AgentEvent(
                "turn_started",
                {"messages": [user_message, draft] if first_turn else [draft]},
            )
            first_turn = False
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
                context_limit=self.context_limit,
                truncate=self.context_limit is not None and is_initial_turn,
            )
            result = None
            async for event in self.session_processor.process(
                session_id=session_id,
                draft_id=draft.id,
                model_id=model_id,
                messages=prompt.messages,
                thinking_strength=thinking_strength,
                tools=prompt.tools,
                request_params=request_params,
                stop_event=stop_event,
            ):
                if event.type == "processor_finished":
                    result = event.data["result"]
                else:
                    yield event
                if event.type == "turn_stopped":
                    return
            if result is None:
                return
            accumulated = result.content
            final_turn = result.turn

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
        if stop_event is not None and stop_event.is_set():
            yield AgentEvent("turn_stopped", {"tool_call_id": call.id})
            return
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
            parameters = inspect.signature(tool.callable).parameters
            if confirmed and "confirmed" in parameters:
                invoke_arguments["confirmed"] = True
            handles_stop = stop_event is not None and "stop_event" in parameters
            if handles_stop:
                invoke_arguments["stop_event"] = stop_event
            result = tool.callable(**invoke_arguments)
            if inspect.isawaitable(result):
                result = await self._await_tool(result, stop_event, handles_stop)
            normalized, raw = self._normalize_result(result)
            status = (
                ToolRunStatus.CANCELLED
                if getattr(result, "cancelled", False)
                else ToolRunStatus.COMPLETED
            )
        except ToolStopped:
            yield AgentEvent("turn_stopped", {"tool_call_id": call.id})
            return
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

    @staticmethod
    async def _await_tool(result, stop_event: asyncio.Event | None, handles_stop: bool):
        if stop_event is None or handles_stop:
            return await result
        task = asyncio.ensure_future(result)
        stop_waiter = asyncio.create_task(stop_event.wait())
        try:
            done, _ = await asyncio.wait(
                {task, stop_waiter}, return_when=asyncio.FIRST_COMPLETED
            )
            if stop_waiter in done and stop_event.is_set():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
                raise ToolStopped
            return task.result()
        finally:
            stop_waiter.cancel()

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
