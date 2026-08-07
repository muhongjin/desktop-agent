# Windows Desktop Agent MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows-first, single-process PySide6/QML desktop Agent that supports OpenAI-compatible streaming chat, automatic per-session workspaces, trusted local file and PowerShell tools, simple permissions, archive-only conversation deletion, and local persistence.

**Architecture:** Keep QML limited to presentation and route all actions through Python application services. The Agent runtime composes a hidden Kernel, global system prompt, history, workspace context, and currently enabled tools; every tool call passes through a PermissionBroker. SQLite stores local data, Windows Credential Manager stores API keys, and future Skill/knowledge/browser/sandbox capabilities receive interfaces but no MVP UI.

**Tech Stack:** Python 3.12, PySide6/QML, `qasync`, `httpx`, `aiosqlite`, `pydantic`, `platformdirs`, `keyring`, `send2trash`, `pywin32`, `pytest`, `pytest-asyncio`, `pytest-qt`, `ruff`, PyInstaller.

---

## File Map

Create the following focused modules. No module should contain UI code and storage or execution policy at the same time.

- `pyproject.toml`: runtime, development, lint, test, and packaging metadata.
- `src/desktop_agent/main.py`: Windows process entry point and Qt/qasync bootstrap.
- `src/desktop_agent/app.py`: application composition root; wires repositories, services, tools, and QML context properties.
- `src/desktop_agent/settings.py`: typed local settings and provider configuration persistence.
- `src/desktop_agent/domain/models.py`: typed session, message, model, tool-run, and permission value objects.
- `src/desktop_agent/storage/database.py`: SQLite connection, WAL pragmas, schema versioning, and transactions.
- `src/desktop_agent/storage/repositories.py`: repository methods for sessions, messages, tool runs, provider settings, and application settings.
- `src/desktop_agent/security/credentials.py`: Windows Credential Manager adapter and test double interface.
- `src/desktop_agent/security/permissions.py`: `none`, `local`, and session full-access policy evaluation.
- `src/desktop_agent/workspaces/service.py`: automatic workspace creation, external-directory association, open-folder action, and recycle-bin deletion.
- `src/desktop_agent/providers/presets.py`: the nine provider presets and model-field metadata.
- `src/desktop_agent/providers/openai_compatible.py`: `/models` discovery, streaming chat, tool-call parsing, timeout, and error normalization.
- `src/desktop_agent/agent/prompt.py`: Kernel loading and prompt composition.
- `src/desktop_agent/agent/loop.py`: stream/tool-call loop, stop handling, persistence hooks, and partial-response finalization.
- `src/desktop_agent/tools/base.py`: tool protocol and capability declarations.
- `src/desktop_agent/tools/files.py`: list/read/write/delete tools with atomic writes.
- `src/desktop_agent/tools/powershell.py`: PowerShell selection, Job Object lifecycle, output capture, and stop handling.
- `src/desktop_agent/tools/registry.py`: static MVP tool registry and model-facing schemas.
- `src/desktop_agent/resources/kernel.md`: hidden minimal runtime instructions.
- `src/desktop_agent/ui/Main.qml`: main application shell.
- `src/desktop_agent/ui/components/SessionList.qml`: active conversation list and archive action.
- `src/desktop_agent/ui/components/ChatView.qml`: message stream and stopped-response rendering.
- `src/desktop_agent/ui/components/ComposerBar.qml`: model, thinking strength, execution mode, full-access, send, stop, and open-workspace controls.
- `src/desktop_agent/ui/components/ToolRunSummary.qml`: collapsed audit summary and expanded details.
- `src/desktop_agent/ui/components/PermissionDialog.qml`: dangerous-operation confirmation.
- `src/desktop_agent/ui/settings/SettingsWindow.qml`: five settings entry points.
- `src/desktop_agent/ui/settings/ModelServicePage.qml`: provider presets, key input, discovery, and custom model IDs.
- `src/desktop_agent/ui/settings/SystemPromptPage.qml`: global prompt editor and reset action.
- `src/desktop_agent/ui/settings/ArchivedChatsPage.qml`: restore and permanent-delete actions.
- `src/desktop_agent/ui/settings/DataWorkspacePage.qml`: local data and default workspace shortcuts.
- `src/desktop_agent/ui/settings/AppSettingsPage.qml`: startup, theme, log directory, and PowerShell selection.
- `tests/unit/test_permissions.py`: policy tests.
- `tests/unit/test_workspaces.py`: workspace/archive/recycle-bin tests.
- `tests/unit/test_prompt.py`: Kernel and context composition tests.
- `tests/unit/test_provider_presets.py`: provider metadata tests.
- `tests/unit/test_shell_selection.py`: PowerShell detection tests.
- `tests/unit/test_atomic_files.py`: atomic write tests.
- `tests/unit/test_repositories.py`: SQLite repository tests.
- `tests/integration/fake_openai_server.py`: deterministic OpenAI-compatible fake service.
- `tests/integration/test_agent_loop.py`: stream, tool call, stop, and error integration tests.
- `tests/ui/test_main_window.py`: Qt smoke tests for the main window and composer controls.
- `tests/conftest.py`: temporary database, workspace, fake credentials, and Qt fixtures.
- `installer/desktop-agent.spec`: PyInstaller packaging configuration.
- `README.md`: Windows setup, development, and local data explanation.

## Task 1: Bootstrap the Python Application

**Files:**
- Create: `pyproject.toml`
- Create: `src/desktop_agent/__init__.py`
- Create: `src/desktop_agent/main.py`
- Create: `src/desktop_agent/resources/kernel.md`
- Create: `tests/conftest.py`
- Test: `tests/unit/test_bootstrap.py`

- [ ] **Step 1: Write the failing bootstrap test**

```python
from desktop_agent.main import build_argument_parser


def test_parser_has_no_server_or_login_flags():
    parser = build_argument_parser()
    args = parser.parse_args([])
    assert not hasattr(args, "port")
    assert not hasattr(args, "login")
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `uv run pytest tests/unit/test_bootstrap.py -q`

Expected: FAIL because the package and parser do not exist.

- [ ] **Step 3: Add the minimal project and entry point**

Define the package metadata with Python `>=3.12`, runtime dependencies listed in the plan header, and development dependencies for pytest, pytest-asyncio, pytest-qt, ruff, and PyInstaller. Implement `build_argument_parser()` with only `--safe-mode` for starting without active tool execution. `main()` must create a `QApplication`, install a qasync event loop, and call an `async def build_application()` function; it must not start an HTTP server.

- [ ] **Step 4: Run the focused test and a module import check**

Run: `uv run pytest tests/unit/test_bootstrap.py -q` and `uv run python -c "import desktop_agent.main; print('import ok')"`

Expected: PASS and `import ok`.

- [ ] **Step 5: Commit**

```text
git add pyproject.toml src tests/unit/test_bootstrap.py
git commit -m "chore: bootstrap desktop agent package"
```

## Task 2: Define Domain Models and SQLite Schema

**Files:**
- Create: `src/desktop_agent/domain/models.py`
- Create: `src/desktop_agent/storage/database.py`
- Create: `src/desktop_agent/storage/repositories.py`
- Test: `tests/unit/test_repositories.py`

- [ ] **Step 1: Write repository tests for the confirmed lifecycle**

Cover these exact cases:

```python
async def test_new_session_is_active_and_has_workspace_id(repo, tmp_path):
    session = await repo.create_session("Draft", str(tmp_path / "session-1"))
    assert session.status is SessionStatus.ACTIVE
    assert session.workspace_path.endswith("session-1")


async def test_archive_and_restore_change_only_session_status(repo, tmp_path):
    session = await repo.create_session("Draft", str(tmp_path / "session-1"))
    await repo.archive_session(session.id)
    assert (await repo.get_session(session.id)).status is SessionStatus.ARCHIVED
    await repo.restore_session(session.id)
    assert (await repo.get_session(session.id)).status is SessionStatus.ACTIVE


async def test_delete_removes_session_messages_and_tool_runs(repo, tmp_path):
    session = await repo.create_session("Draft", str(tmp_path / "session-1"))
    await repo.append_message(session.id, MessageRole.USER, "hello")
    await repo.append_tool_run(session.id, "list_files", {"path": "."}, "ok", ToolRunStatus.COMPLETED)
    await repo.archive_session(session.id)
    await repo.delete_session(session.id)
    assert await repo.get_session(session.id) is None
    assert await repo.list_messages(session.id) == []
    assert await repo.list_tool_runs(session.id) == []


async def test_message_keeps_model_snapshot_and_role(repo, tmp_path):
    session = await repo.create_session("Draft", str(tmp_path / "session-1"))
    message = await repo.append_message(
        session.id,
        MessageRole.ASSISTANT,
        "answer",
        model_id="deepseek-chat",
        thinking_strength="medium",
        request_params={"temperature": 0.2},
    )
    assert message.role is MessageRole.ASSISTANT
    assert message.model_id == "deepseek-chat"
    assert message.request_params == {"temperature": 0.2}


async def test_tool_message_and_tool_run_have_distinct_storage_purposes(repo, tmp_path):
    session = await repo.create_session("Draft", str(tmp_path / "session-1"))
    message = await repo.append_message(session.id, MessageRole.TOOL, "2 files")
    run = await repo.append_tool_run(
        session.id, "list_files", {"path": "."}, "raw command output", ToolRunStatus.COMPLETED
    )
    assert message.content == "2 files"
    assert run.raw_output == "raw command output"
```

The tests must assert that deletion is only callable for an archived session and that an active session raises `InvalidSessionState`:

```python
async def test_active_session_cannot_be_deleted(repo, tmp_path):
    session = await repo.create_session("Draft", str(tmp_path / "session-1"))
    with pytest.raises(InvalidSessionState):
        await repo.delete_session(session.id)
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `uv run pytest tests/unit/test_repositories.py -q`

Expected: FAIL because schema, models, and repository methods are absent.

- [ ] **Step 3: Implement typed domain models**

Create enums `SessionStatus(active, archived)`, `MessageRole(user, assistant, tool)`, `MessageStatus(complete, stopped)`, and `ToolRunStatus(completed, failed, cancelled)`. Define models for `Session`, `Message`, `ToolRun`, `ProviderConfig`, and `AppSetting`. Store per-message `model_id`, `thinking_strength`, a JSON object containing only non-secret request parameters, and a boolean `completion_marker`. An assistant draft is persisted with `status=stopped` and `completion_marker=false`; a completed response changes both to `complete` and `true`.

- [ ] **Step 4: Implement the SQLite schema and repositories**

Create tables `sessions`, `messages`, `tool_runs`, `provider_configs`, `app_settings`, and `schema_meta`. Enable `PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON`, and a busy timeout. Use parameterized statements and explicit transactions. `delete_session()` must verify `archived` before deleting rows; workspace deletion is performed by `WorkspaceService`, not the repository. The repository interface is `create_session(title, workspace_path)`, `get_session(session_id)`, `archive_session(session_id)`, `restore_session(session_id)`, `delete_session(session_id)`, `append_message(session_id, role, content, model_id=None, thinking_strength=None, request_params=None, status=MessageStatus.COMPLETE, completion_marker=True)`, `update_message(message_id, content, status, completion_marker)`, `append_tool_run(session_id, tool_name, input_json, raw_output, status)`, `list_messages(session_id)`, and `list_tool_runs(session_id)`.

- [ ] **Step 5: Run the repository tests and inspect the schema**

Run: `uv run pytest tests/unit/test_repositories.py -q`

Expected: PASS. Verify with a temporary database that WAL is enabled and deleting an archived session cascades messages and tool runs.

- [ ] **Step 6: Commit**

```text
git add src/desktop_agent/domain src/desktop_agent/storage tests/unit/test_repositories.py
git commit -m "feat: add local session persistence"
```

## Task 3: Add Paths, Credentials, and Workspace Lifecycle

**Files:**
- Create: `src/desktop_agent/settings.py`
- Create: `src/desktop_agent/security/credentials.py`
- Create: `src/desktop_agent/workspaces/service.py`
- Test: `tests/unit/test_workspaces.py`
- Test: `tests/unit/test_credentials.py`

- [ ] **Step 1: Write path and workspace tests**

Test that `platformdirs.user_data_dir()` is used for the database and workspaces, every session gets a UUID-named workspace, an associated external directory is normalized and never deleted, and an archived session can be moved to the recycle bin only through the service.

```python
def test_create_workspace_uses_session_id(service, tmp_path):
    path = service.create_for_session("session-1")
    assert path == tmp_path / "workspaces" / "session-1"
    assert path.is_dir()


def test_associate_external_directory_is_normalized(service, tmp_path):
    external = tmp_path / "project"
    external.mkdir()
    associated = service.associate_external_directory("session-1", external / ".." / "project")
    assert associated == external.resolve()


def test_delete_archived_workspace_calls_recycle_bin_adapter(service, fake_recycle_bin):
    service.create_for_session("session-1")
    service.repository.archive_session("session-1")
    service.delete_archived_workspace("session-1")
    assert fake_recycle_bin.deleted == [service.workspace_path("session-1")]


def test_delete_active_workspace_is_rejected(service):
    service.create_for_session("session-1")
    with pytest.raises(InvalidSessionState):
        service.delete_archived_workspace("session-1")
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `uv run pytest tests/unit/test_workspaces.py tests/unit/test_credentials.py -q`

Expected: FAIL because the services do not exist.

- [ ] **Step 3: Implement settings and Credential Manager adapters**

Use `platformdirs.user_data_dir("<AppName>")` for local storage. Implement `CredentialStore.get(provider_id)`, `set(provider_id, secret)`, and `delete(provider_id)` through `keyring`. Keep provider configuration rows free of secrets. Tests must inject an in-memory fake credential store and must never access a real key.

- [ ] **Step 4: Implement `WorkspaceService`**

Implement `WorkspaceService(root_dir, session_repository, recycle_bin_adapter)` with `create_for_session(session_id)`, `associate_external_directory(session_id, path)`, `open_workspace(session_id)`, and `delete_archived_workspace(session_id)`. `delete_archived_workspace()` loads the session and rejects any status other than `archived`. Use `send2trash.send2trash()` for the automatic workspace. Permit zero or one associated external directory. Never pass the external directory to `send2trash`.

- [ ] **Step 5: Run workspace and credential tests**

Run: `uv run pytest tests/unit/test_workspaces.py tests/unit/test_credentials.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```text
git add src/desktop_agent/settings.py src/desktop_agent/security src/desktop_agent/workspaces tests/unit
git commit -m "feat: add local credentials and session workspaces"
```

## Task 4: Implement Provider Presets and OpenAI-Compatible Streaming

**Files:**
- Create: `src/desktop_agent/providers/presets.py`
- Create: `src/desktop_agent/providers/openai_compatible.py`
- Create: `src/desktop_agent/providers/__init__.py`
- Test: `tests/unit/test_provider_presets.py`
- Test: `tests/integration/fake_openai_server.py`
- Test: `tests/integration/test_provider_client.py`

- [ ] **Step 1: Write preset and client tests**

Assert that all nine named presets expose a Base URL, display name, model hint list, and discovery support. Test streaming text deltas, streamed tool-call deltas, `/models` success, `/models` failure with manual fallback, timeout, and non-2xx error conversion.

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `uv run pytest tests/unit/test_provider_presets.py tests/integration/test_provider_client.py -q`

Expected: FAIL because the preset registry and client are absent.

- [ ] **Step 3: Implement provider metadata**

Define immutable `ProviderPreset` records for OpenAI, Gemini, OpenRouter, Ollama, DeepSeek, Bailian, Moonshot, Zhipu, and SiliconFlow. Presets may suggest models but must not hard-code credentials. Keep the client input as `base_url`, `api_key`, `model_id`, `thinking_strength`, messages, and tools.

- [ ] **Step 4: Implement the HTTP client and SSE parser**

Use one `httpx.AsyncClient`. Implement `discover_models()` against the configured Base URL and `stream_chat()` against the chat-completions endpoint. Parse `data:` SSE frames, collect text deltas and tool-call argument fragments by tool-call ID, and emit a final `AssistantTurn` object. Never retry a failed request in MVP. Strip API keys from raised error messages and logs.

- [ ] **Step 5: Run the provider tests**

Run: `uv run pytest tests/unit/test_provider_presets.py tests/integration/test_provider_client.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```text
git add src/desktop_agent/providers tests/unit/test_provider_presets.py tests/integration
git commit -m "feat: add OpenAI-compatible providers"
```

## Task 5: Build Permission Policy and File Tools

**Files:**
- Create: `src/desktop_agent/security/permissions.py`
- Create: `src/desktop_agent/tools/base.py`
- Create: `src/desktop_agent/tools/files.py`
- Create: `src/desktop_agent/tools/registry.py`
- Test: `tests/unit/test_permissions.py`
- Test: `tests/unit/test_atomic_files.py`

- [ ] **Step 1: Write policy and atomic-write tests**

Cover `none` read-only behavior, local workspace read/write, associated-directory read/write, full-access path expansion, confirmation for high-risk paths, path traversal rejection, and atomic replacement when a write succeeds.

```python
def test_none_allows_read_but_rejects_write(policy, workspace):
    read = policy.evaluate(PermissionRequest("fs.read", workspace / "a.txt"), SessionAccess.none(workspace))
    write = policy.evaluate(PermissionRequest("fs.write", workspace / "a.txt"), SessionAccess.none(workspace))
    assert read is PermissionDecision.ALLOW
    assert write is PermissionDecision.DENY


def test_local_allows_workspace_write(policy, workspace):
    request = PermissionRequest("fs.write", workspace / "a.txt")
    assert policy.evaluate(request, SessionAccess.local(workspace)) is PermissionDecision.ALLOW


def test_associated_directory_is_trusted(policy, external_dir):
    request = PermissionRequest("fs.write", external_dir / "a.txt")
    access = SessionAccess.local(Path("C:/session"), associated_directory=external_dir)
    assert policy.evaluate(request, access) is PermissionDecision.ALLOW


def test_full_access_still_confirms_system_change(policy):
    request = PermissionRequest("process.exec", Path("C:/Windows/System32"), risk="system-change")
    assert policy.evaluate(request, SessionAccess.full_access(Path("C:/session"))) is PermissionDecision.CONFIRM


def test_write_uses_temp_file_then_replace(files, target):
    files.write_file(target, "new content")
    assert target.read_text() == "new content"
    assert list(target.parent.glob(f".{target.name}.*.tmp")) == []
```

- [ ] **Step 2: Run policy tests and verify they fail**

Run: `uv run pytest tests/unit/test_permissions.py tests/unit/test_atomic_files.py -q`

Expected: FAIL because the policy and tools do not exist.

- [ ] **Step 3: Implement capability and permission types**

Define capabilities `fs.read`, `fs.write`, `fs.delete`, and `process.exec`, plus `PermissionDecision(ALLOW, DENY, CONFIRM)`, `PermissionRequest(capability, path, risk)`, and `SessionAccess.none(workspace)`, `SessionAccess.local(workspace, associated_directory=None)`, and `SessionAccess.full_access(workspace)`. `PermissionBroker.evaluate(request, access)` returns a decision. `none` allows reads inside the automatic workspace or associated directory only; it denies writes, deletes, and process execution. `local` allows trusted reads and writes, while dangerous paths and operations return `CONFIRM`. Full access removes path restrictions but does not bypass confirmation for privilege escalation, system configuration, or high-risk deletion.

- [ ] **Step 4: Implement file tools**

Implement list, read, write, and delete tools. Resolve paths with `Path.resolve()`, reject traversal outside allowed roots, write to a same-directory temporary file, flush and replace atomically, and return a structured result containing path, byte count, and diff summary. Delete must never bypass PermissionBroker.

- [ ] **Step 5: Register model-facing tool schemas**

Create a static registry containing only the four MVP file tools and expose JSON schemas with explicit required fields. The registry returns tool metadata and a callable; it does not import QML or execute anything itself.

- [ ] **Step 6: Run the policy and file tests**

Run: `uv run pytest tests/unit/test_permissions.py tests/unit/test_atomic_files.py -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```text
git add src/desktop_agent/security/permissions.py src/desktop_agent/tools tests/unit/test_permissions.py tests/unit/test_atomic_files.py
git commit -m "feat: add permission policy and file tools"
```

## Task 6: Add PowerShell 5.1/7 Execution with Job Objects

**Files:**
- Create: `src/desktop_agent/tools/powershell.py`
- Test: `tests/unit/test_shell_selection.py`
- Test: `tests/integration/test_powershell_tool.py`

- [ ] **Step 1: Write shell-selection and cancellation tests**

Mock `shutil.which()` to verify `pwsh.exe` is preferred, `powershell.exe` is the fallback, and an explicit setting overrides detection. On Windows integration tests, run `Write-Output`, assert stdout and exit code, then start a sleeping child and assert Job Object termination.

- [ ] **Step 2: Run the tests and verify they fail**

Run: `uv run pytest tests/unit/test_shell_selection.py tests/integration/test_powershell_tool.py -q`

Expected: FAIL because the executor is absent; skip the Windows-only integration test on non-Windows CI.

- [ ] **Step 3: Implement executable selection**

Implement `select_shell(mode)` with `auto`, `windows-powershell`, and `pwsh`. In auto mode call `shutil.which("pwsh")`, then `shutil.which("powershell")`, and raise a readable `ShellUnavailable` error if neither exists.

- [ ] **Step 4: Implement Job Object process management**

Use `pywin32` `win32job` APIs to create a Job Object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, assign the PowerShell process, capture stdout/stderr asynchronously, and close the Job Object on stop or application shutdown. Start PowerShell with `-NoLogo -NoProfile -NonInteractive -Command` and never change execution policy globally.

- [ ] **Step 5: Run shell tests**

Run: `uv run pytest tests/unit/test_shell_selection.py -q` on every platform and `uv run pytest tests/integration/test_powershell_tool.py -q` on Windows.

Expected: PASS; non-Windows reports the platform-specific integration test as skipped.

- [ ] **Step 6: Commit**

```text
git add src/desktop_agent/tools/powershell.py tests/unit/test_shell_selection.py tests/integration/test_powershell_tool.py
git commit -m "feat: add managed PowerShell execution"
```

## Task 7: Compose Prompts and Implement the Agent Loop

**Files:**
- Create: `src/desktop_agent/agent/prompt.py`
- Create: `src/desktop_agent/agent/loop.py`
- Test: `tests/unit/test_prompt.py`
- Test: `tests/integration/test_agent_loop.py`

- [ ] **Step 1: Write prompt and loop tests**

Assert that the request order is Kernel, global prompt, recent history, workspace context, then current tools; Kernel never appears in QML settings; per-message model snapshots are preserved; a tool call passes through PermissionBroker; stop keeps partial text and prevents subsequent tool calls; and a provider error returns a visible error without retry.

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `uv run pytest tests/unit/test_prompt.py tests/integration/test_agent_loop.py -q`

Expected: FAIL because `PromptComposer` and `AgentLoop` are absent.

- [ ] **Step 3: Implement `PromptComposer`**

Load `resources/kernel.md` from the package, read the global prompt from `AppSettings`, add only the current session’s recent messages, and add workspace metadata without dumping directory contents. Add tool schemas only for capabilities allowed by the current mode. Keep the Kernel and global prompt separate in the request object.

- [ ] **Step 4: Implement the streaming loop**

For each user message: persist the user row, create an assistant draft with `status=stopped` and `completion_marker=false`, compose the request, stream assistant text and update the draft content after each delta batch, accumulate tool calls, ask `PermissionBroker`, execute the selected tool, persist a normalized `tool` message and a full `tool_runs` audit row, then continue the provider request. On a successful final response, update the draft to `status=complete` and `completion_marker=true`. Emit Qt-agnostic events `text_delta`, `tool_started`, `tool_finished`, `permission_required`, `turn_finished`, and `turn_stopped`.

- [ ] **Step 5: Implement stop and partial-response behavior**

Use an `asyncio.Event` cancellation token. When set, cancel the HTTP stream, terminate the current PowerShell Job Object, keep the accumulated assistant text with `status=stopped`, set `completion_marker=true` for an intentional user stop, and never replay the unfinished turn. On a later application start, any assistant row with `status=stopped` and `completion_marker=false` is rendered with “响应已停止”.

- [ ] **Step 6: Run agent integration tests**

Run: `uv run pytest tests/unit/test_prompt.py tests/integration/test_agent_loop.py -q`

Expected: PASS against the deterministic fake provider.

- [ ] **Step 7: Commit**

```text
git add src/desktop_agent/agent src/desktop_agent/resources tests/unit/test_prompt.py tests/integration/test_agent_loop.py
git commit -m "feat: add prompt composition and agent loop"
```

## Task 8: Wire the Application Services and QML Shell

**Files:**
- Create: `src/desktop_agent/app.py`
- Create: `src/desktop_agent/ui/Main.qml`
- Create: `src/desktop_agent/ui/components/SessionList.qml`
- Create: `src/desktop_agent/ui/components/ChatView.qml`
- Create: `src/desktop_agent/ui/components/ComposerBar.qml`
- Create: `src/desktop_agent/ui/components/ToolRunSummary.qml`
- Create: `src/desktop_agent/ui/components/PermissionDialog.qml`
- Test: `tests/ui/test_main_window.py`

- [ ] **Step 1: Write Qt smoke tests**

Launch the QML shell with fake services and assert that the window contains the session list, chat view, model selector, thinking-strength selector, execution-mode selector, full-access toggle, send button, stop button, and open-workspace action.

- [ ] **Step 2: Run the UI test and verify it fails**

Run: `uv run pytest tests/ui/test_main_window.py -q`

Expected: FAIL because the QML files and application composition are absent.

- [ ] **Step 3: Implement the composition root**

In `build_application()`, create the database, repositories, credential store, workspace service, provider service, permission broker, tool registry, AgentLoop, and QML engine. Expose only service façades as context properties. Keep test doubles injectable through constructor arguments.

- [ ] **Step 4: Implement the main QML shell**

Build the confirmed two-column layout. Bind session selection to `SessionService`, message events to `ChatView`, composer controls to the current session’s model and execution mode, and the full-access toggle to an in-memory session permission state.

- [ ] **Step 5: Implement collapsed tool summaries and permission dialogs**

Render one-line summaries by default. Expand to show the normalized command, paths, output, exit code, and permission decision. Only show `PermissionDialog` for `CONFIRM`; `ALLOW` and `DENY` remain silent or show a compact result.

- [ ] **Step 6: Run the UI smoke test**

Run: `uv run pytest tests/ui/test_main_window.py -q`

Expected: PASS with fake services and no network access.

- [ ] **Step 7: Commit**

```text
git add src/desktop_agent/app.py src/desktop_agent/ui tests/ui/test_main_window.py
git commit -m "feat: add desktop chat shell"
```

## Task 9: Implement Settings and Archive Screens

**Files:**
- Create: `src/desktop_agent/ui/settings/SettingsWindow.qml`
- Create: `src/desktop_agent/ui/settings/ModelServicePage.qml`
- Create: `src/desktop_agent/ui/settings/SystemPromptPage.qml`
- Create: `src/desktop_agent/ui/settings/ArchivedChatsPage.qml`
- Create: `src/desktop_agent/ui/settings/DataWorkspacePage.qml`
- Create: `src/desktop_agent/ui/settings/AppSettingsPage.qml`
- Modify: `src/desktop_agent/app.py`
- Test: `tests/ui/test_settings_window.py`
- Test: `tests/integration/test_archive_flow.py`

- [ ] **Step 1: Write settings and archive tests**

Assert that the settings window exposes exactly five entries, model discovery failure enables manual model entry, API keys never appear in the provider model, the system prompt reset restores the packaged default, archived chats can be restored, and only archived chats can be deleted.

- [ ] **Step 2: Run the tests and verify they fail**

Run: `uv run pytest tests/ui/test_settings_window.py tests/integration/test_archive_flow.py -q`

Expected: FAIL because settings pages and archive façades are absent.

- [ ] **Step 3: Implement model settings**

Create provider-specific forms backed by one `ProviderConfigService`. Save only Base URL, model metadata, and Credential Manager references. Use a discovery button that calls `/models`; on error preserve the entered Base URL and show a manual model ID field.

- [ ] **Step 4: Implement global prompt and application settings**

Bind the editor to `app_settings.system_prompt`, provide a reset action that loads the packaged default, and add startup, theme, log-directory, and Shell selection fields. Do not add login, sync, export, or import controls.

- [ ] **Step 5: Implement archive and data screens**

Show archived sessions with Restore and Delete. Delete calls `WorkspaceService.delete_archived_workspace()` and `SessionRepository.delete_session()` only after the service moves the automatic workspace to the system recycle bin. Do not expose a system recycle-bin cleanup button.

- [ ] **Step 6: Run settings and archive tests**

Run: `uv run pytest tests/ui/test_settings_window.py tests/integration/test_archive_flow.py -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```text
git add src/desktop_agent/app.py src/desktop_agent/ui/settings tests/ui tests/integration/test_archive_flow.py
git commit -m "feat: add model settings and archived chats"
```

## Task 10: Add Packaging, Documentation, and End-to-End Smoke Tests

**Files:**
- Create: `installer/desktop-agent.spec`
- Create: `tests/e2e/test_mvp_smoke.py`
- Create: `README.md`
- Modify: `pyproject.toml`

- [ ] **Step 1: Write the Windows smoke test**

The test must create a new session, configure a fake OpenAI-compatible endpoint, send a prompt that causes a file write and PowerShell command, expand the tool summary, archive the session, restore it, close the app, reopen the same database, and assert the conversation remains visible. Use fakes for the provider and Credential Manager in CI.

- [ ] **Step 2: Run the smoke test and verify it fails**

Run: `uv run pytest tests/e2e/test_mvp_smoke.py -q`

Expected: FAIL until the packaged composition root and all service bindings are complete.

- [ ] **Step 3: Add the PyInstaller configuration**

Include the QML directory, `resources/kernel.md`, Qt plugins, and the `pywin32` hooks. Set the executable to launch `desktop_agent.main:main`, do not open a console window, and write user data only under `platformdirs.user_data_dir()`.

- [ ] **Step 4: Document development and local-data behavior**

README must explain `uv sync`, `uv run python -m desktop_agent`, the five settings pages, model API traffic, Credential Manager storage, session workspace paths, archive/delete behavior, and the fact that MVP has no login or cloud sync.

- [ ] **Step 5: Run all checks**

Run:

```text
uv run ruff format .
uv run ruff check .
uv run pytest -q
uv run pyinstaller installer/desktop-agent.spec --noconfirm
```

Expected: formatting produces no diff, Ruff exits 0, tests pass, and the Windows executable is created under `dist/`.

- [ ] **Step 6: Perform the manual acceptance flow**

On Windows, install the generated executable and verify: the app opens without a server; unconfigured model state is visible in the input bar; a new session creates a workspace; local file and PowerShell tools work; full access is session-scoped; tool summaries expand; model switching affects only later messages; archive/restore works; delete moves only the automatic workspace to the recycle bin; restarting preserves the conversation.

- [ ] **Step 7: Commit**

```text
git add installer README.md pyproject.toml tests/e2e
git commit -m "feat: package Windows desktop agent MVP"
```

## Plan Self-Review

- Spec coverage: all confirmed sections are mapped to Tasks 1–10. Skills, knowledge base, browser, sandbox, plugins, IM, voice, login, and sync remain explicitly out of scope.
- Placeholder scan: no `TBD`, `TODO`, or undefined “appropriate handling” steps are used.
- Type consistency: `SessionStatus`, `MessageRole`, `MessageStatus`, `ToolRunStatus`, `PermissionBroker.evaluate()`, `WorkspaceService`, `CredentialStore`, `PromptComposer`, and `AgentLoop` are introduced before their UI consumers.
- Recovery consistency: no task adds automatic retry or re-execution; stopped text is persisted and rendered as ended on restart.
- Security consistency: associated directories are trusted for read/write, full access removes path limits only, and high-risk confirmation remains mandatory.
