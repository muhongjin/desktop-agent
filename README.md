# Desktop Agent

Windows 优先的本地桌面 Agent。应用使用 PySide6/QML 构建，UI、Agent Runtime、权限策略和本地存储运行在同一进程中，不启动本地 HTTP 服务，也不需要登录。

当前版本：`v1.0.0`

## v1.0.0 更新

- 新增本地知识库（RAG）：导入文档 → 解析 → 递归字符切分 → 嵌入 → 混合检索 → 带引用回答，数据全部保存在本机。
- 支持 `.txt` / `.md` / `.pdf` / `.docx` / `.xlsx`；按知识库管理文档，可查看分块、索引进度与失败原因。
- 嵌入模型自动发现：选择模型服务后从 `/models` 自动筛选支持 `/embeddings` 的模型，失败场景提供手动输入兜底。
- 检索采用稠密向量 + SQLite FTS5 稀疏检索（中文 trigram）+ RRF 融合，默认返回 5 条，可在知识库设置中调整。
- 每个知识库可配置分块大小、重复段大小和返回条数；返回条数立即生效。
- 对话输入区可按会话勾选知识库；回答下方展示引用来源（文档 / 章节 / 页码 / 片段）。
- 检索失败自动降级为普通对话，不阻塞回答；安全模式下不启用知识库。
- 新增知识库设计文档与完整测试（`176 passed, 5 skipped`）。

## 历史版本

### v0.1.1（2026-08-14）

- 重构 Agent 会话处理：`AgentLoop` 负责多轮循环，`SessionProcessor` 负责单次 LLM 流式请求，`SessionRetry` 负责错误分类与重试退避。
- 网络、限流和服务端临时错误最多总尝试五次；上下文超限与不可重试错误会直接结束，并保留已经收到的部分输出。
- Windows 应用改为单实例运行，重复启动不会创建多个独立进程窗口。
- 精简未使用的 Qt/PySide6 模块和 QML 资源，显著减小便携版与安装包体积。
- 使用新的应用图标，覆盖窗口标题栏、任务栏、EXE、安装程序、快捷方式和卸载项。
- 修复流式消息完成时的界面闪烁，以及安装完成页取消“启动”后仍会启动应用的问题。

### v0.1.0（2026-08-10）

- 首个公开发行版：PySide6/QML 单进程桌面 Agent、OpenAI-compatible 流式对话、文件与 PowerShell 工具、权限模式、工作区与会话归档。

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

设置窗口包含六个入口：模型服务、系统提示词、已归档聊天、数据与工作区、应用、知识库。

模型服务共用 OpenAI-compatible API，内置 OpenAI、Gemini、OpenRouter、Ollama、DeepSeek、阿里云百炼、Moonshot、智谱和 SiliconFlow 预设。应用优先通过 `/models` 发现模型，失败后可以手动输入模型 ID。

API Key 只保存到 Windows Credential Manager，不写入 SQLite。配置云模型后，对话内容会发送到对应模型服务；账户、会话和文件数据仍保存在本机。MVP 没有登录、账户、云同步、导入或导出功能。

应用不设置固定默认模型。新会话继承最近一次选择的模型和思考强度，执行模式固定从 `local` 开始；会话中切换只影响之后发送的消息，每条消息保留实际使用的模型快照。

## 知识库（RAG）

设置页「知识库」入口可以创建多个知识库：

- 创建时选择模型服务，并从自动获取的模型列表中挑选支持 `/embeddings` 的嵌入模型；列表会过滤聊天模型和 rerank 模型，必要时可手动输入模型 ID。
- 支持导入 `.txt`、`.md`、`.markdown`、`.pdf`、`.docx`、`.xlsx`；单文件上限 64 MB，同库按内容 SHA-256 去重。
- 文档解析后按递归字符切分（默认 512 字符、重叠 50 字符），逐批生成嵌入；导入页面显示索引进度和失败原因。
- 检索流程：查询向量 + FTS5 稀疏检索 → RRF 融合 → 相似度过滤与相邻块合并 → 按预算注入；检索失败会降级为普通对话。
- 每个知识库可设置分块大小、重复段大小和返回条数；分块参数只影响之后导入的文档，返回条数立即生效。
- 在「检索测试」页可以直接验证检索结果；对话输入区可挑选当前会话启用的知识库，回答下方展示引用来源。
- 嵌入与检索会调用所配置的模型服务（使用 Ollama 等本地服务时数据不出本机）；知识库文档副本与索引保存在本机数据目录。

## 权限与工作区

每个会话自动创建独立目录：

```text
%LOCALAPPDATA%/DesktopAgent/workspaces/<session-id>/
```

输入栏可以选择 `none`、`local` 或 `all`：

- `none`：仅允许读取自动工作区和关联目录，禁用写入与命令执行。
- `local`：允许可信目录内读写和普通命令，高风险操作需要确认。
- `all`：解除路径限制，但提权、系统修改和高风险删除仍需确认；关闭应用或归档会话后失效。

PowerShell 自动优先使用 `pwsh.exe`，不存在时回退到 `powershell.exe`。也可以在设置中显式选择 Windows PowerShell 5.1 或 PowerShell 7+。应用不修改系统执行策略。

## 本地数据

SQLite 数据库和自动工作区位于 `platformdirs.user_data_dir("DesktopAgent")`。SQLite 使用 WAL 模式。设置中的“数据与工作区”可以直接打开数据目录和默认工作区目录。

知识库索引独立保存在同一数据目录下的 `knowledge.sqlite3`，导入文档的原始副本位于 `knowledge/<知识库ID>/docs/`。

活跃会话不能直接删除，只能先归档。已归档聊天可以恢复或删除；删除时自动工作区会进入系统回收站，随后删除会话记录。关联的外部目录永远不会随会话删除，应用也不提供清空系统回收站的操作。

模型连接因网络、限流或服务端临时故障失败时，单次回复最多总尝试五次。应用异常退出后不会重放文件操作或重新执行命令，已生成的内容和完整会话历史会保留。

## 打包

正式发行需要 Python 3.12、`uv` 和 Inno Setup 6。先安装开发依赖，再执行统一构建脚本：

```powershell
uv sync
pwsh -File installer/build-release.ps1
```

Windows PowerShell 5.1 使用相同脚本：

```powershell
powershell -ExecutionPolicy Bypass -File installer\build-release.ps1
```

如果 Inno Setup 不在默认目录，通过 `-InnoSetupCompiler` 传入 `ISCC.exe` 的完整路径。只构建便携目录时可以添加 `-PortableOnly`。

发行文件统一写入：

```text
artifacts/
├─ DesktopAgent-1.0.0-win64/
├─ DesktopAgent-Portable-1.0.0-win64.zip
└─ DesktopAgent-Setup-1.0.0.exe
```

安装包采用每用户安装，默认目录为 `%LOCALAPPDATA%\Programs\Desktop Agent`，无需管理员权限。卸载器会删除程序文件和快捷方式，但保留 `%LOCALAPPDATA%\DesktopAgent` 中的会话、工作区和设置。便携目录避免每次启动解压整个运行时，分发时必须保留其完整目录结构。
