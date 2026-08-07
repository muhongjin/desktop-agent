# Windows 桌面 Agent MVP 设计

日期：2026-08-07

状态：已确认

## 1. 目标

构建一个面向普通电脑用户的本地桌面 Agent。用户只需安装并启动一个 Windows 软件，不需要启动服务、配置端口或使用命令行。

MVP 必须完成以下闭环：

```text
安装 → 配置模型 → 对话 → Agent 创建或修改文件
→ 执行 PowerShell → 检查工具记录
→ 关闭应用 → 重启并继续历史会话
```

产品强调：

- 单应用、低配置门槛
- 精简且可控的系统提示词
- 清晰但不过度打扰的权限体验
- 本地数据与会话工作区
- 可审计的文件和命令操作

## 2. MVP 范围

### 2.1 包含

- Windows 桌面安装包
- PySide6/QML 单进程界面
- OpenAI-compatible 模型配置与流式对话
- 全局系统提示词和隐藏 Kernel
- 自动会话工作区与现有目录关联
- 文件读取、写入和目录操作
- Windows PowerShell 5.1、PowerShell 7+ 与 `cmd.exe` 回退
- `none`、`local` 和会话级完全访问
- 折叠式工具执行记录
- 会话归档、恢复和删除
- SQLite 持久化
- Windows Credential Manager 密钥存储

### 2.2 不包含

- 知识库、Embedding 和 Reranker
- 网页搜索和浏览器控制
- `sandbox` 执行器
- Skill 加载
- 插件系统
- 聊天软件连接
- 语音
- 账户、登录和云同步

不在 MVP 内的能力只保留内部接口边界，不在界面中显示空入口或“即将推出”。

## 3. 技术路线

采用 Python 3.12、PySide6、QML 和 `asyncio` 构建单进程桌面应用。应用主体只有一个进程；执行 PowerShell 工具时可以创建受控子进程。

选择该路线的原因：

- 用户不需要面对本地 Web 服务或前后端部署
- Agent、文档处理、知识库和 Skill 的后续能力可以继续使用 Python 生态
- UI、权限、会话和工具执行共享一个进程内状态
- 避免 Tauri Sidecar 或 Electron 与 Python 运行时之间的 IPC、更新和崩溃恢复成本

应用内部仍保持明确的 UI、业务服务、Agent Core 和系统适配层边界。

## 4. 总体架构

```text
QML UI
  │ Qt signals/slots
  ▼
Application Services
  ├── SessionService
  ├── ModelService
  ├── WorkspaceService
  └── SettingsService
  │
  ▼
Agent Runtime
  ├── PromptComposer
  ├── AgentLoop
  ├── ToolRegistry
  └── PermissionBroker
  │
  ▼
Adapters
  ├── OpenAICompatibleClient
  ├── FileTools
  ├── PowerShellExecutor
  ├── SQLiteRepository
  ├── WindowsCredentialStore
  └── RecycleBinAdapter
```

架构约束：

- QML 只负责展示和用户交互，业务规则不写入 QML
- UI 只能调用 Application Services
- AgentLoop 只能通过 ToolRegistry 使用系统能力
- 所有工具执行必须经过 PermissionBroker
- 数据库、文件系统、Shell、凭据和回收站操作通过 Adapter 完成
- 应用不启动 HTTP 服务

后续为 `AuthService`、`SkillManager`、`KnowledgeBaseService`、`BrowserService` 和 `SandboxExecutor` 预留接口。

## 5. 主界面

采用对话优先的双栏结构：

- 左侧显示活跃会话
- 中间显示对话内容
- 输入区提供模型、思考强度和执行模式选择
- 输入区提供发送、停止和打开工作区操作
- 工具执行默认显示一行折叠摘要
- 用户可以展开查看命令、文件改动、输出和授权记录
- 会话级完全访问按钮位于执行模式附近，开启后显示明显状态

应用不提供独立 Web 后台、端口设置或命令行启动要求。

## 6. 模型配置

底层只实现一套 OpenAI-compatible Client。

首版提供以下配置预设：

- OpenAI
- Gemini
- OpenRouter
- Ollama
- DeepSeek
- 阿里云百炼
- Moonshot
- 智谱
- SiliconFlow

预设之间只区分 Base URL、模型建议、字段提示和帮助文本，不实现多套协议。

模型列表优先通过 `/models` 自动发现。发现失败时，用户可以手动输入模型 ID，并保存自定义模型。

应用不设置固定默认模型。它记录最近一次模型和思考强度选择，新会话继承该状态。会话中允许切换模型和思考强度，切换只影响后续消息。每条消息保存实际使用的模型、思考强度和非敏感请求参数，不保存 API Key 或认证请求头。

模型不支持思考强度时，控件自动隐藏或禁用。

尚未配置模型时，应用仍直接进入主界面。输入区显示“请先配置模型”，点击后打开模型设置。

API Key 保存到 Windows Credential Manager。数据库只保存凭据引用。正常读取不要求用户输入 Windows 密码，也不触发管理员权限弹窗。

## 7. Prompt 设计

每次模型请求由以下内容组成：

```text
隐藏 Kernel
+ 全局系统提示词
+ 最近对话上下文
+ 当前工作区信息
+ 当前会话可用工具
```

隐藏 Kernel 只包含稳定且必要的运行规则，不包含冗长教程、完整工具手册或所有未来功能说明。

设置页只向用户展示一份可编辑的全局系统提示词，并提供恢复默认值操作。隐藏 Kernel 不在界面中展示。

权限边界由 PermissionBroker 执行，不依赖模型遵守提示词。

## 8. Agent Loop

```text
用户消息
  ↓
模型流式输出
  ↓
是否请求工具？
  ├── 否 → 保存并完成回复
  └── 是 → PermissionBroker → 执行工具
              ↓
           工具结果返回模型 → 继续循环
```

用户可以停止当前回复。停止后保留已经生成的内容，不继续调用工具。

工具调用结果默认折叠，但完整记录可随时展开。AgentLoop 不直接访问文件系统或启动进程。

## 9. 权限模型

### 9.1 `none`

- 允许读取自动会话工作区和已关联目录
- 关闭文件写入
- 关闭命令执行
- 保留普通模型对话

### 9.2 `local`

- 自动会话工作区内的读写自动允许
- 用户主动关联的现有目录直接加入可信读写范围
- 越界访问、提权、系统配置和高风险删除需要确认

### 9.3 本会话完全访问

- 解除目录范围限制
- 可以访问当前 Windows 用户本身有权访问的文件
- 可以执行普通命令
- 提权、系统配置和高风险删除仍需确认
- 授权只保存在内存中；关闭应用、归档该聊天或手动关闭开关后失效

`sandbox` 模式不在 MVP 中实现，后续通过独立的 `SandboxExecutor` 接入。

## 10. 工作区

每个新会话自动生成一个独立工作区：

```text
%LOCALAPPDATA%/<AppName>/workspaces/<session-id>/
```

用户无需理解或选择路径。界面提供“打开工作区”快捷操作。

用户可以为会话关联零个或一个现有目录。关联动作本身即表示授予该会话对目录的可信读写权限，不复制目录内容。

关联目录以规范化绝对路径保存。应用绝不因为删除会话而删除关联目录。

## 11. 会话生命周期

主会话列表不提供直接删除：

```text
活跃会话
  └── 归档 → 已归档聊天
                  ├── 恢复 → 活跃会话
                  └── 删除 → 删除记录 + 自动工作区移入系统回收站
```

删除后的会话不提供应用内恢复功能。用户仍可通过系统回收站处理自动工作区文件。

关联的外部目录不受归档、恢复或删除影响。

## 12. 进程退出与写入安全

MVP 不设计自动重试、运行恢复或“重新执行”按钮。任何失败或中断的 Agent 回合都不会自动重发模型请求。

应用异常退出时：

- 保留已经生成的回复内容
- 重新打开后移除加载状态
- 在未完成回复末尾显示“响应已停止”
- 不自动重放模型请求、文件操作或 PowerShell 命令
- 用户可以直接继续对话，由 Agent 根据当前文件状态重新判断下一步

应用控制的文件替换使用同目录临时文件，写入成功后执行原子替换。任意 PowerShell 命令无法保证事务性，因此退出后绝不自动重放。

PowerShellExecutor 使用 Windows Job Object 管理完整进程树。应用退出或用户停止回复时终止 Job Object 中的所有子进程。工具记录只用于审计，不参与恢复流程。

## 13. PowerShell 执行

自动选择策略：

1. 优先检测并使用 `pwsh.exe`
2. 未安装 PowerShell 7+ 时使用 `powershell.exe`
3. 必要时使用 `cmd.exe` 作为兼容回退

设置页允许选择：

- 自动
- Windows PowerShell 5.1
- PowerShell 7+

每条命令记录实际使用的 Shell、参数、退出码、标准输出和标准错误。

## 14. 数据模型

### 14.1 `sessions`

- ID
- 标题
- 状态：`active` 或 `archived`
- 自动工作区路径
- 关联目录
- 当前模型与思考强度
- 创建和更新时间

### 14.2 `messages`

- ID 与 Session ID
- `message_role`：`user`、`assistant` 或 `tool`
- 内容
- 实际模型与思考强度
- 工具调用关联
- 状态：`complete` 或 `stopped`
- 创建时间

`message_role` 是模型协议中的消息身份，不是人格。隐藏 Kernel 和全局系统提示词不作为普通聊天消息保存，而是在请求时动态构建 `system` 消息。

`tool` 消息只保存需要重新发送给模型的规范化工具结果。`tool_runs` 保存完整审计信息，包括原始输入、输出、退出码和权限判断，避免两个位置承担相同职责。

### 14.3 `tool_runs`

- ID 与消息关联
- 工具名称
- 输入和输出
- 权限模式
- 实际 Shell
- 退出码
- 开始和结束时间
- 结果状态

### 14.4 `provider_configs`

- 服务商预设
- Base URL
- 模型列表与自定义模型
- Credential Manager 引用

### 14.5 `app_settings`

- 全局系统提示词
- 最近模型与思考强度
- Shell 选择
- 主题与应用设置

SQLite 使用 WAL 模式。数据库操作通过 Repository 完成。

## 15. 设置页

设置页只包含以下五个入口：

1. 模型服务
2. 系统提示词
3. 已归档聊天
4. 数据与工作区
5. 应用

“数据与工作区”提供查看数据目录和打开默认工作区目录。应用不提供清空系统回收站的操作。导出与导入不在 MVP 中实现。

“应用”提供开机启动、主题、日志目录和 PowerShell 选择。

第一版的账户、会话和文件数据完全保存在本地，无需登录。用户配置云模型时，对话内容仍会发送到对应模型服务。内部可以定义 `AuthService` 接口，但不显示登录入口，也不实现同步逻辑。

## 16. 错误处理

- 模型请求失败时，在对话中显示可读错误
- 不自动重试失败的模型请求，也不自动重放工具调用
- PowerShell 非零退出码作为工具结果返回 Agent，不导致应用崩溃
- 权限拒绝显示被拒绝的能力和授权入口
- API Key 等敏感字段从日志中移除
- 数据库或设置损坏时停止相关写入并显示明确错误，不静默覆盖

## 17. 测试策略

### 17.1 单元测试

- Prompt 拼装与 Kernel 分层
- 权限模式、可信目录和完全访问
- 会话归档、恢复和删除
- 原子文件替换
- 模型配置与模型发现回退
- PowerShell 5.1/7 自动选择
- API Key 日志脱敏

### 17.2 集成测试

- 使用假 OpenAI-compatible 服务验证流式输出和工具循环
- 使用临时 SQLite 数据库验证持久化与 WAL
- 使用临时目录验证工作区生命周期
- 验证 Credential Manager Adapter 的成功与失败路径
- 验证 PowerShell 退出码、输出和取消行为

### 17.3 UI 与发布测试

- 未配置模型时的主界面状态
- 新会话、模型切换和思考强度切换
- 工具摘要展开
- 会话归档、恢复和删除
- 打开工作区和关联目录
- Windows 安装、启动、关闭、升级和卸载冒烟测试

## 18. 后续子项目

后续能力分别编写独立规格，不并入本 MVP：

```text
MVP 桌面 Agent
  → Skill 兼容
  → 原生知识库
  → 网页搜索与读取
  → 浏览器插件控制
  → Sandbox
  → 可选账户与同步
```

每个后续子项目复用本设计中的 Application Service、Tool Registry、Permission Broker 和 Adapter 边界。
