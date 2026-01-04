<p align="center">
  <img src="assets/icon.svg" width="80" height="96" alt="Kiro Proxy">
</p>

<h1 align="center">Kiro API Proxy</h1>

<p align="center">
  Kiro IDE API 反向代理服务器，支持多账号轮询、会话粘性、429自动切换
</p>

<p align="center">
  <a href="#功能特性">功能</a> •
  <a href="#快速开始">快速开始</a> •
  <a href="#cli-配置">CLI 配置</a> •
  <a href="#api-端点">API</a> •
  <a href="#许可证">许可证</a>
</p>

---

## 功能特性

- **多协议支持** - OpenAI / Anthropic / Gemini 三种协议兼容
- **多账号轮询** - 支持添加多个 Kiro 账号，自动负载均衡
- **会话粘性** - 同一会话 60 秒内使用同一账号，保持上下文
- **429 自动切换** - 遇到限流自动切换到其他可用账号
- **Web UI** - 简洁的管理界面，支持对话测试、监控、日志查看
- **Token 扫描** - 自动扫描系统中的 Kiro token 文件
- **跨平台** - 支持 Windows / macOS / Linux

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
python app.py
```

启动后访问 http://localhost:8000

### 登录获取 Token

1. 打开 Kiro IDE
2. 点击登录，使用 Google/GitHub 账号
3. 登录成功后 token 自动保存到 `~/.aws/sso/cache/`
4. 在 Web UI 点击「扫描 Token」添加账号

## CLI 配置

### 模型对照表

| Kiro 模型 | 能力 | Claude Code | Codex | Gemini CLI |
|-----------|------|-------------|-------|------------|
| `claude-sonnet-4` | ⭐⭐⭐ 推荐 | `claude-sonnet-4` | `gpt-4o` | `gemini-2.0-flash` |
| `claude-sonnet-4.5` | ⭐⭐⭐⭐ 更强 | `claude-sonnet-4.5` | `gpt-4o` | `gemini-1.5-pro` |
| `claude-haiku-4.5` | ⚡ 快速 | `claude-haiku-4.5` | `gpt-4o-mini` | `gemini-1.5-flash` |
| `claude-opus-4.5` | ⭐⭐⭐⭐⭐ 最强 | `claude-opus-4.5` | `o1` | `gemini-2.0-flash-thinking` |

### Claude Code 配置

```
名称: Kiro Proxy
API Key: any
Base URL: http://localhost:8000
模型: claude-sonnet-4
```

### Codex 配置

```
名称: Kiro Proxy
API Key: any
Endpoint: http://localhost:8000/v1
模型: gpt-4o
```

### Gemini CLI 配置

```
名称: Kiro Proxy
API Key: any
Base URL: http://localhost:8000
模型: gemini-2.0-flash
```

## API 端点

| 协议 | 端点 | 用途 |
|------|------|------|
| OpenAI | `POST /v1/chat/completions` | Codex CLI |
| OpenAI | `GET /v1/models` | 模型列表 |
| Anthropic | `POST /v1/messages` | Claude Code CLI |
| Gemini | `POST /v1/models/{model}:generateContent` | Gemini CLI |

### cURL 示例

```bash
# OpenAI 格式
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-sonnet-4", "messages": [{"role": "user", "content": "Hello"}]}'

# Anthropic 格式
curl http://localhost:8000/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: any" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model": "claude-sonnet-4", "max_tokens": 1024, "messages": [{"role": "user", "content": "Hello"}]}'
```

### Python 示例

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="not-needed")
response = client.chat.completions.create(
    model="claude-sonnet-4",
    messages=[{"role": "user", "content": "Hello"}]
)
print(response.choices[0].message.content)
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
