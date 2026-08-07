# Desktop Agent

Windows 优先的本地桌面 Agent。应用使用 PySide6/QML 构建，UI、Agent Runtime、权限策略和本地存储运行在同一进程中，不启动本地 HTTP 服务，也不需要登录。

## 开发运行

需要 Python 3.12 和 [uv](https://docs.astral.sh/uv/)。

```powershell
uv sync
uv run desktop-agent
```

安全模式会禁用全部工具，只保留模型对话：

```powershell
uv run desktop-agent --safe-mode
```

运行测试与静态检查：

```powershell
uv run pytest -q
uv run ruff check .
```

## 模型配置

设置窗口包含五个入口：模型服务、系统提示词、已归档聊天、数据与工作区、应用。

模型服务共用 OpenAI-compatible API，内置 OpenAI、Gemini、OpenRouter、Ollama、DeepSeek、阿里云百炼、Moonshot、智谱和 SiliconFlow 预设。应用优先通过 `/models` 发现模型，失败后可以手动输入模型 ID。

API Key 只保存到 Windows Credential Manager，不写入 SQLite。配置云模型后，对话内容会发送到对应模型服务；账户、会话和文件数据仍保存在本机。MVP 没有登录、账户、云同步、导入或导出功能。

应用不设置固定默认模型。新会话继承最近一次选择的模型、思考强度和执行模式；会话中切换只影响之后发送的消息，每条消息保留实际使用的模型快照。

## 权限与工作区

每个会话自动创建独立目录：

```text
%LOCALAPPDATA%/DesktopAgent/workspaces/<session-id>/
```

输入栏可以选择 `none` 或 `local`，并可为当前会话临时开启完全访问：

- `none`：仅允许读取自动工作区和关联目录，禁用写入与命令执行。
- `local`：允许可信目录内读写和普通命令，高风险操作需要确认。
- 完全访问：解除路径限制，但提权、系统修改和高风险删除仍需确认；关闭应用或归档会话后失效。

PowerShell 自动优先使用 `pwsh.exe`，不存在时回退到 `powershell.exe`。也可以在设置中显式选择 Windows PowerShell 5.1 或 PowerShell 7+。应用不修改系统执行策略。

## 本地数据

SQLite 数据库和自动工作区位于 `platformdirs.user_data_dir("DesktopAgent")`。SQLite 使用 WAL 模式。设置中的“数据与工作区”可以直接打开数据目录和默认工作区目录。

活跃会话不能直接删除，只能先归档。已归档聊天可以恢复或删除；删除时自动工作区会进入系统回收站，随后删除会话记录。关联的外部目录永远不会随会话删除，应用也不提供清空系统回收站的操作。

应用异常退出后不会自动重试模型请求、重放文件操作或重新执行命令。已生成的部分回复会保留，并显示“响应已停止”。

## 打包

```powershell
uv run pyinstaller installer/desktop-agent.spec --noconfirm
```

生成的无控制台 Windows 程序位于 `dist/DesktopAgent.exe`。
