<p align="center">
  <img src="assets/icon.svg" width="80" height="96" alt="Kiro Proxy">
</p>

<h1 align="center">Kiro API Proxy</h1>

<p align="center">
  Kiro IDE API 反向代理服务器，支持多账号轮询、Token 自动刷新、配额管理
</p>

<p align="center">
  <a href="#功能特性">功能</a> •
  <a href="#快速开始">快速开始</a> •
  <a href="#cli-配置">CLI 配置</a> •
  <a href="#api-端点">API</a> •
  <a href="#许可证">许可证</a>
</p>

---

> **⚠️ 测试说明**
> 
> 本项目主要针对 **Claude Code (VSCode 插件版)** 进行测试，工具调用功能已验证可用。
> 
> 其他客户端（Codex CLI、Gemini CLI、Claude Code CLI 等）理论上兼容，但未经充分测试，如遇问题欢迎反馈。

## 功能特性

### 核心功能
- **多协议支持** - OpenAI / Anthropic / Gemini 三种协议兼容
- **工具调用支持** - 支持 Claude Code 的工具调用功能
- **多账号轮询** - 支持添加多个 Kiro 账号，自动负载均衡
- **会话粘性** - 同一会话 60 秒内使用同一账号，保持上下文
- **Web UI** - 简洁的管理界面，支持对话测试、监控、日志查看

### v1.4.0 新功能
- **Token 预刷新** - 后台每 5 分钟检查，提前 15 分钟自动刷新
- **健康检查** - 每 10 分钟检测账号可用性，自动标记状态
- **请求统计增强** - 按账号/模型统计，24 小时趋势
- **请求重试机制** - 网络错误/5xx 自动重试，指数退避

### v1.3.0 功能
- **Token 自动刷新** - 检测过期自动刷新，支持 Social 认证
- **动态 Machine ID** - 每个账号独立指纹，基于凭证 + 时间因子生成
- **配额管理** - 429 自动检测、冷却 (300s)、自动恢复
- **自动账号切换** - 配额超限时自动切换到下一个可用账号
- **配置持久化** - 账号配置保存到 `~/.kiro-proxy/config.json`，重启不丢失
- **凭证状态管理** - Active / Cooldown / Unhealthy / Disabled 四种状态

## 已知限制

### 对话长度限制

Kiro API 有输入长度限制。当对话历史过长时，会返回错误：

```
Input is too long. (CONTENT_LENGTH_EXCEEDS_THRESHOLD)
```

**这是 Kiro 服务端的限制，无法绕过。**

#### 解决方案

1. **清空对话历史** - 在 Claude Code 中输入 `/clear` 清空当前会话
2. **恢复工作进度** - 清空后，告诉 Claude 你之前在做什么，它会读取代码文件恢复上下文
3. **预防措施** - 复杂任务分阶段完成，每个阶段结束后 `/clear` 开始新会话

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

启动后访问 http://localhost:8080

### 登录获取 Token

1. 打开 Kiro IDE
2. 点击登录，使用 Google/GitHub 账号
3. 登录成功后 token 自动保存到 `~/.aws/sso/cache/`
4. 在 Web UI 点击「扫描 Token」添加账号

## CLI 配置

### 模型对照表

| Kiro 模型 | 能力 | Claude Code | Codex |
|-----------|------|-------------|-------|
| `claude-sonnet-4` | ⭐⭐⭐ 推荐 | `claude-sonnet-4` | `gpt-4o` |
| `claude-sonnet-4.5` | ⭐⭐⭐⭐ 更强 | `claude-sonnet-4.5` | `gpt-4o` |
| `claude-haiku-4.5` | ⚡ 快速 | `claude-haiku-4.5` | `gpt-4o-mini` |
| `claude-opus-4.5` | ⭐⭐⭐⭐⭐ 最强 | `claude-opus-4.5` | `o1` |

### Claude Code 配置

```
名称: Kiro Proxy
API Key: any
Base URL: http://localhost:8080
模型: claude-sonnet-4
```

### Codex 配置

```
名称: Kiro Proxy
API Key: any
Endpoint: http://localhost:8080/v1
模型: gpt-4o
```

## API 端点

| 协议 | 端点 | 用途 |
|------|------|------|
| OpenAI | `POST /v1/chat/completions` | Codex CLI |
| OpenAI | `GET /v1/models` | 模型列表 |
| Anthropic | `POST /v1/messages` | Claude Code |
| Anthropic | `POST /v1/messages/count_tokens` | Token 计数 |
| Gemini | `POST /v1/models/{model}:generateContent` | Gemini CLI |

### 管理 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/accounts` | GET | 获取所有账号状态 |
| `/api/accounts/{id}` | GET | 获取账号详情 |
| `/api/accounts/{id}/refresh` | POST | 刷新账号 Token |
| `/api/accounts/{id}/restore` | POST | 恢复账号（从冷却状态） |
| `/api/accounts/refresh-all` | POST | 刷新所有即将过期的 Token |
| `/api/quota` | GET | 获取配额状态 |
| `/api/stats` | GET | 获取统计信息 |
| `/api/stats/detailed` | GET | 获取详细统计（按账号/模型） |
| `/api/health-check` | POST | 手动触发健康检查 |
| `/api/logs` | GET | 获取请求日志 |

## 项目结构

```
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
│   └── retry.py              # 重试机制
│
├── credential/                # 凭证管理
│   ├── types.py              # KiroCredentials
│   ├── fingerprint.py        # Machine ID 生成
│   ├── quota.py              # 配额管理器
│   └── refresher.py          # Token 刷新
│
├── providers/                 # Provider 抽象
│   ├── base.py               # BaseProvider 基类
│   └── kiro.py               # Kiro Provider
│
├── handlers/                  # API 处理器
│   ├── anthropic.py          # /v1/messages
│   ├── openai.py             # /v1/chat/completions
│   ├── gemini.py             # /v1/models/{model}:generateContent
│   └── admin.py              # 管理 API
│
└── web/
    └── html.py               # Web UI (组件化单文件)
```

## 构建

```bash
# 安装构建依赖
pip install pyinstaller

# 构建
python build.py
```

输出文件在 `dist/` 目录。

## 免责声明

本项目仅供学习研究，禁止商用。使用本项目产生的任何后果由使用者自行承担，与作者无关。

本项目与 Kiro / AWS / Anthropic 官方无关。
