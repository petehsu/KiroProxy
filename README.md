
<p align="center">
  <img src="assets/icon.svg" width="80" height="96" alt="Kiro Proxy">
</p>

<h1 align="center">Kiro API Proxy</h1>

<p align="center">
  面向开发者工作流的开源兼容层与路由服务，支持多账号轮询、Token 自动刷新、配额管理，以及 OpenAI / Anthropic / Gemini 协议适配
</p>

<p align="center">
  <a href="#功能特性">功能</a> •
  <a href="#快速开始">快速开始</a> •
  <a href="#cli-配置">CLI 配置</a> •
  <a href="#api-端点">API</a> •
  <a href="#项目结构">项目结构</a> •
  <a href="#许可证">许可证</a>
</p>

<p align="center">
  <strong>中文</strong> | <a href="README_EN.md">English</a>
</p>

---

Kiro API Proxy 是一个面向开发者工具链的开源兼容层与请求路由服务，用于将 Kiro 相关能力接入常见的 LLM 客户端工作流中。项目重点关注协议兼容、认证管理、请求路由、配额控制，以及多账号场景下的稳定维护体验。

它可以作为 Claude Code、Codex CLI、Gemini CLI 等客户端的统一接入层，帮助开发者在真实使用场景中更方便地完成调试、切换、监控和维护。

> **⚠️ 测试说明**
>
> 本项目当前支持 **Claude Code**、**Codex CLI**、**Gemini CLI** 三种客户端，工具调用功能已全面支持。

## 功能特性

### 核心功能
- **多协议支持** - OpenAI / Anthropic / Gemini 三种协议兼容
- **完整工具调用** - 三种协议的工具调用能力全面支持
- **图片理解** - 支持 Claude Code / Codex CLI 图片输入
- **网络搜索** - 支持 Claude Code / Codex CLI 网络搜索工具
- **多账号轮询** - 支持添加多个 Kiro 账号并自动负载均衡
- **会话粘性** - 同一会话 60 秒内优先使用同一账号，保持上下文连续性
- **Web UI** - 提供简洁管理界面，支持监控、日志、设置
- **多语言界面** - 支持中文和英文界面切换

### v1.8.1 新功能
- **每账号独立代理** - 每个 Kiro 账号可配置独立的代理服务器 (HTTP/SOCKS5)
  - 账号代理优先级高于全局代理，留空则回退到全局代理或直连
  - Web UI 支持在线设置/编辑每个账号的代理
  - API: `PUT /api/accounts/{id}/proxy`
  - 所有请求路径均支持：API 调用、Token 刷新、健康检查、用量查询

### v1.8.0 新功能
- **动态模型解析** - 4 层管线：标准化→缓存→别名→透传
- **Payload 大小守卫** - 检测 615KB 限制 + 自动裁剪
- **截断恢复** - 检测截断响应 + 注入合成消息
- **VPN/代理支持** - 全局 HTTP/SOCKS5 代理
- **loguru 日志系统** - 结构化日志，级别/文件/调试模式
- **.env 配置** - python-dotenv 环境变量管理
- **Docker 部署** - Dockerfile + docker-compose
- **tiktoken Token 计数** - 替代粗估，中文计数更准确
- **Extended Thinking FSM** - 有限状态机解析器
- **kiro-cli SQLite 认证** - 集成 kiro-cli 数据库
- **Prompt Caching** - cache_control → cachePoint 转换
- **Tool Search** - regex + BM25 工具搜索
- **Circuit Breaker** - 指数退避 + 概率重试
- **Pydantic 数据验证** - 请求/响应模型校验
- **类型提示改进** - 全面类型注解

### v1.7.2 新功能
- **多语言支持** - Web UI 完整支持中英文切换
- **双语启动器** - 支持端口/语言设置，提供更清晰的启动入口
- **英文帮助文档** - 全部 5 篇文档已翻译为英文

### v1.7.1 新功能
- **Windows 支持补强** - 注册表浏览器检测 + PATH 回退，兼容便携版
- **打包资源修复** - PyInstaller 打包后可正常加载图标与内置文档
- **Token 扫描稳定性** - 修复 Windows 路径编码处理问题

### v1.6.3 新功能
- **命令行工具 (CLI)** - 无 GUI 环境下也能轻松管理服务与账号
  - `python run.py accounts list` - 列出账号
  - `python run.py accounts export/import` - 导出/导入账号
  - `python run.py accounts add` - 交互式添加 Token
  - `python run.py accounts scan` - 扫描本地 Token
  - `python run.py login google/github` - 命令行登录
  - `python run.py login remote` - 生成远程登录链接
- **远程登录链接** - 可在有浏览器的机器上完成授权，Token 自动同步
- **账号导入导出** - 支持跨机器迁移账号配置
- **手动添加 Token** - 支持直接粘贴 accessToken / refreshToken

### v1.6.2 新功能
- **Codex CLI 完整支持** - 使用 OpenAI Responses API（`/v1/responses`）
  - 完整工具调用支持（shell、file 等所有工具）
  - 图片输入支持（`input_image` 类型）
  - 网络搜索支持（`web_search` 工具）
  - 错误代码映射（rate_limit、context_length 等）
- **Claude Code 增强** - 图片理解和网络搜索完整支持
  - 支持 Anthropic 和 OpenAI 两种图片格式
  - 支持 `web_search` / `web_search_20250305` 工具

### v1.6.1 新功能
- **请求限速** - 通过限制请求频率降低账号风险
  - 每账号最小请求间隔
  - 每账号每分钟最大请求数
  - 全局每分钟最大请求数
  - Web UI 设置页面可配置
- **账号异常检测** - 自动检测 `TEMPORARILY_SUSPENDED` 等错误
  - 友好的错误日志输出
  - 自动禁用异常账号
  - 自动切换到其他可用账号
- **统一错误处理** - 三种协议使用统一的错误分类和处理逻辑

### v1.6.0 功能
- **历史消息管理** - 提供 4 种策略处理对话长度限制，可自由组合
  - 自动截断：发送前优先保留最新上下文并摘要前文，必要时按数量/字符数截断
  - 智能摘要：用 AI 生成早期对话摘要，保留关键信息
  - 摘要缓存：历史变化不大时复用最近摘要，减少重复 LLM 调用（默认启用）
  - 错误重试：遇到长度错误时自动截断重试（默认启用）
  - 预估检测：预估 token 数量，超限预先截断
- **Gemini 工具调用** - 完整支持 `functionDeclarations` / `functionCall` / `functionResponse`
- **设置页面** - Web UI 新增设置标签页，可配置历史消息管理策略

### v1.5.0 功能
- **用量查询** - 查询账号配额使用情况，显示已用 / 余额 / 使用率
- **多登录方式** - 支持 Google / GitHub / AWS Builder ID 三种登录方式
- **流量监控** - 完整的 LLM 请求监控，支持搜索、过滤、导出
- **浏览器选择** - 自动检测已安装浏览器，支持无痕模式
- **文档中心** - 内置帮助文档，支持左侧目录与右侧 Markdown 渲染

### v1.4.0 功能
- **Token 预刷新** - 后台每 5 分钟检查，提前 15 分钟自动刷新
- **健康检查** - 每 10 分钟检测账号可用性，自动标记状态
- **请求统计增强** - 支持按账号 / 模型统计及 24 小时趋势
- **请求重试机制** - 网络错误 / 5xx 自动重试，使用指数退避

## 工具调用支持

| 功能 | Anthropic (Claude Code) | OpenAI (Codex CLI) | Gemini |
|------|------------------------|-------------------|--------|
| 工具定义 | ✅ `tools` | ✅ `tools.function` | ✅ `functionDeclarations` |
| 工具调用响应 | ✅ `tool_use` | ✅ `tool_calls` | ✅ `functionCall` |
| 工具结果 | ✅ `tool_result` | ✅ `tool` 角色消息 | ✅ `functionResponse` |
| 强制工具调用 | ✅ `tool_choice` | ✅ `tool_choice` | ✅ `toolConfig.mode` |
| 工具数量限制 | ✅ 50 个 | ✅ 50 个 | ✅ 50 个 |
| 历史消息修复 | ✅ | ✅ | ✅ |
| 图片理解 | ✅ | ✅ | ❌ |
| 网络搜索 | ✅ | ✅ | ❌ |

## 已知限制

### 对话长度限制

Kiro API 存在输入长度限制。当对话历史过长时，可能会返回如下错误：

```text
Input is too long. (CONTENT_LENGTH_EXCEEDS_THRESHOLD)
````

#### 自动处理（v1.6.0+）

代理内置了历史消息管理功能，可在「设置」页面配置：

* **错误重试**（默认）：遇到长度错误时自动截断并重试
* **智能摘要**：用 AI 生成早期对话摘要，保留关键信息
* **摘要缓存**（默认）：历史变化不大时复用最近摘要，减少重复 LLM 调用
* **自动截断**：每次请求前优先保留最新上下文并摘要前文，必要时按数量 / 字符数截断
* **预估检测**：预估 token 数量，超限时预先截断

摘要缓存可通过以下配置项调整（默认值）：

* `summary_cache_enabled`: `true`
* `summary_cache_min_delta_messages`: `3`
* `summary_cache_min_delta_chars`: `4000`
* `summary_cache_max_age_seconds`: `180`

#### 手动处理

1. 在 Claude Code 中输入 `/clear` 清空对话历史
2. 告诉 AI 你之前在做什么，它会读取代码文件恢复上下文

## 快速开始

### 方式一：下载预编译版本

从 [Releases](../../releases) 下载对应平台的安装包，解压后直接运行。

### 方式二：从源码运行

```bash
# 克隆项目
git clone https://github.com/yourname/kiro-proxy.git
cd kiro-proxy

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 运行
python run.py

# 或指定端口
python run.py 8081
```

启动后访问：

```text
http://localhost:8080
```

### 命令行工具 (CLI)

无 GUI 环境可使用 CLI 管理账号和服务：

```bash
# 账号管理
python run.py accounts list                 # 列出账号
python run.py accounts export -o acc.json   # 导出账号
python run.py accounts import acc.json      # 导入账号
python run.py accounts add                  # 交互式添加 Token
python run.py accounts scan --auto          # 扫描并自动添加本地 Token

# 登录
python run.py login google                  # Google 登录
python run.py login github                  # GitHub 登录
python run.py login remote --host myserver.com:8080  # 生成远程登录链接

# 服务
python run.py serve                         # 启动服务（默认 8080）
python run.py serve -p 8081                 # 指定端口
python run.py status                        # 查看状态
```

### 登录获取 Token

**方式一：在线登录（推荐）**

1. 打开 Web UI，点击「在线登录」
2. 选择登录方式：Google / GitHub / AWS Builder ID
3. 在浏览器中完成授权
4. 账号自动添加

**方式二：扫描 Token**

1. 打开 Kiro IDE，使用 Google / GitHub 账号登录
2. 登录成功后 token 自动保存到 `~/.aws/sso/cache/`
3. 在 Web UI 点击「扫描 Token」添加账号

## CLI 配置

### 模型对照表

| Kiro 模型             | 能力       | Claude Code         | Codex         |
| ------------------- | -------- | ------------------- | ------------- |
| `claude-sonnet-4`   | ⭐⭐⭐ 推荐   | `claude-sonnet-4`   | `gpt-4o`      |
| `claude-sonnet-4.5` | ⭐⭐⭐⭐ 更强  | `claude-sonnet-4.5` | `gpt-4o`      |
| `claude-haiku-4.5`  | ⚡ 快速     | `claude-haiku-4.5`  | `gpt-4o-mini` |
| `claude-opus-4.5`   | ⭐⭐⭐⭐⭐ 最强 | `claude-opus-4.5`   | `o1`          |

### Claude Code 配置

```text
名称: Kiro Proxy
API Key: any
Base URL: http://localhost:8080
模型: claude-sonnet-4
```

### Codex 配置

Codex CLI 使用 OpenAI Responses API，配置如下：

```bash
# 设置环境变量
export OPENAI_API_KEY=any
export OPENAI_BASE_URL=http://localhost:8080/v1

# 运行 Codex
codex
```

或在 `~/.codex/config.toml` 中配置：

```toml
[providers.openai]
api_key = "any"
base_url = "http://localhost:8080/v1"
```

## API 端点

| 协议        | 端点                                        | 用途                       |
| --------- | ----------------------------------------- | ------------------------ |
| OpenAI    | `POST /v1/chat/completions`               | Chat Completions API     |
| OpenAI    | `POST /v1/responses`                      | Responses API（Codex CLI） |
| OpenAI    | `GET /v1/models`                          | 模型列表                     |
| Anthropic | `POST /v1/messages`                       | Claude Code              |
| Anthropic | `POST /v1/messages/count_tokens`          | Token 计数                 |
| Gemini    | `POST /v1/models/{model}:generateContent` | Gemini CLI               |

### 管理 API

| 端点                           | 方法   | 说明              |
| ---------------------------- | ---- | --------------- |
| `/api/accounts`              | GET  | 获取所有账号状态        |
| `/api/accounts/{id}`         | GET  | 获取账号详情          |
| `/api/accounts/{id}/usage`   | GET  | 获取账号用量信息        |
| `/api/accounts/{id}/refresh` | POST | 刷新账号 Token      |
| `/api/accounts/{id}/restore` | POST | 恢复账号（从冷却状态）     |
| `/api/accounts/refresh-all`  | POST | 刷新所有即将过期的 Token |
| `/api/flows`                 | GET  | 获取流量记录          |
| `/api/flows/stats`           | GET  | 获取流量统计          |
| `/api/flows/{id}`            | GET  | 获取流量详情          |
| `/api/quota`                 | GET  | 获取配额状态          |
| `/api/stats`                 | GET  | 获取统计信息          |
| `/api/health-check`          | POST | 手动触发健康检查        |
| `/api/browsers`              | GET  | 获取可用浏览器列表       |
| `/api/docs`                  | GET  | 获取文档列表          |
| `/api/docs/{id}`             | GET  | 获取文档内容          |

## 项目结构

```text
kiro_proxy/
├── main.py                    # FastAPI 应用入口
├── config.py                  # 全局配置
├── converters.py              # 协议转换
│
├── core/                      # 核心模块
│   ├── account.py            # 账号管理
│   ├── state.py              # 全局状态
│   ├── persistence.py        # 配置持久化
│   ├── scheduler.py          # 后台任务调度
│   ├── stats.py              # 请求统计
│   ├── retry.py              # 重试机制
│   ├── browser.py            # 浏览器检测
│   ├── flow_monitor.py       # 流量监控
│   └── usage.py              # 用量查询
│
├── credential/                # 凭证管理
│   ├── types.py              # KiroCredentials
│   ├── fingerprint.py        # Machine ID 生成
│   ├── quota.py              # 配额管理器
│   └── refresher.py          # Token 刷新
│
├── auth/                      # 认证模块
│   └── device_flow.py        # Device Code Flow / Social Auth
│
├── handlers/                  # API 处理器
│   ├── anthropic.py          # /v1/messages
│   ├── openai.py             # /v1/chat/completions
│   ├── responses.py          # /v1/responses（Codex CLI）
│   ├── gemini.py             # /v1/models/{model}:generateContent
│   └── admin.py              # 管理 API
│
├── cli.py                     # 命令行工具
│
├── docs/                      # 内置文档
│   ├── 01-quickstart.md      # 快速开始
│   ├── 02-features.md        # 功能特性
│   ├── 03-faq.md             # 常见问题
│   └── 04-api.md             # API 参考
│
└── web/
    └── html.py               # Web UI（组件化单文件）
```

## 构建

```bash
# 安装构建依赖
pip install pyinstaller

# 构建
python build.py
```

输出文件位于 `dist/` 目录。

## 适用场景

* 将 Kiro 相关能力接入 Claude Code、Codex CLI、Gemini CLI 等客户端
* 在多账号场景下进行统一请求路由与管理
* 需要对 Token 刷新、配额状态、健康检查进行集中维护
* 希望为开发者工作流提供统一的兼容层和可观测性能力

## 免责声明

本项目仅供学习与研究用途，请在遵守相关服务条款与适用规则的前提下使用。使用本项目产生的任何后果由使用者自行承担，与作者无关。

本项目与 Kiro / AWS / Anthropic / Google / OpenAI 官方无直接关联。
