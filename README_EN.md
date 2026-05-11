<p align="center">
  <img src="assets/icon.svg" width="80" height="96" alt="Kiro Proxy">
</p>

<h1 align="center">Kiro API Proxy</h1>

<p align="center">
  An open-source compatibility and routing layer for developer workflows, with multi-account rotation, token auto-refresh, quota management, and protocol adaptation for OpenAI / Anthropic / Gemini
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#cli-configuration">CLI Configuration</a> •
  <a href="#api-endpoints">API</a> •
  <a href="#project-structure">Project Structure</a> •
  <a href="#license">License</a>
</p>

<p align="center">
  <a href="README.md">中文</a> | <strong>English</strong>
</p>

---

Kiro API Proxy is an open-source compatibility and request routing layer for developer tooling workflows. It is designed to connect Kiro-related capabilities with common LLM client workflows, with a focus on protocol compatibility, authentication management, request routing, quota control, and operational stability in multi-account environments.

It can serve as a unified integration layer for tools such as Claude Code, Codex CLI, and Gemini CLI, making it easier to debug, switch, monitor, and maintain real-world developer workflows.

> **⚠️ Testing Note**
>
> This project currently supports **Claude Code**, **Codex CLI**, and **Gemini CLI**, with full tool-calling support.

## Features

### Core Features
- **Multi-protocol support** - Compatible with OpenAI / Anthropic / Gemini protocols
- **Full tool-calling support** - Complete tool-calling support across all three protocols
- **Image understanding** - Supports image input for Claude Code / Codex CLI
- **Web search** - Supports web search tools for Claude Code / Codex CLI
- **Multi-account rotation** - Add multiple Kiro accounts with automatic load balancing
- **Session stickiness** - Reuses the same account within 60 seconds for the same session to preserve context continuity
- **Web UI** - A clean admin interface with monitoring, logs, and settings
- **Multilingual interface** - Supports both Chinese and English UI switching

### What's New in v1.8.1
- **Per-account proxy** - Each Kiro account can have its own proxy server (HTTP/SOCKS5)
  - Account proxy takes priority over the global proxy; leave empty to fall back to global proxy or direct connection
  - Web UI supports inline proxy editing per account
  - API: `PUT /api/accounts/{id}/proxy`
  - Covers all request paths: API calls, token refresh, health checks, usage queries

### What's New in v1.8.0
- **Dynamic model resolution** - 4-layer pipeline: normalize → cache → alias → pass-through
- **Payload size guard** - 615KB limit detection + auto-trimming
- **Truncation recovery** - Detect truncated responses + inject synthetic recovery messages
- **VPN/Proxy support** - Global HTTP/SOCKS5 proxy
- **loguru logging** - Structured logging with levels, file output, debug mode
- **.env configuration** - python-dotenv environment variable management
- **Docker deployment** - Dockerfile + docker-compose
- **tiktoken token counting** - Accurate token counting (replaces rough estimation)
- **Extended Thinking FSM** - Finite state machine parser
- **kiro-cli SQLite auth** - Integration with kiro-cli database
- **Prompt Caching** - cache_control → cachePoint conversion
- **Tool Search** - regex + BM25 tool search
- **Circuit Breaker** - Exponential backoff + probabilistic retry
- **Pydantic validation** - Request/response model validation
- **Type hints** - Comprehensive type annotations

### What's New in v1.7.2
- **Multilingual support** - Full Chinese / English switching in the Web UI
- **Bilingual launcher** - Port / language settings with clearer launch actions
- **English documentation** - All 5 built-in docs have been translated into English

### What's New in v1.7.1
- **Improved Windows support** - Registry browser detection + PATH fallback, including portable browser support
- **Packaging resource fixes** - Icons and built-in docs now load correctly after PyInstaller packaging
- **More stable token scanning** - Fixed Windows path encoding issues

### What's New in v1.6.3
- **Command-line interface (CLI)** - Easy management in headless or server environments
  - `python run.py accounts list` - List accounts
  - `python run.py accounts export/import` - Export / import accounts
  - `python run.py accounts add` - Add token interactively
  - `python run.py accounts scan` - Scan local tokens
  - `python run.py login google/github` - Log in from the command line
  - `python run.py login remote` - Generate a remote login link
- **Remote login links** - Complete authorization on a browser-enabled machine and sync tokens automatically
- **Account import/export** - Migrate account configurations across machines
- **Manual token input** - Paste accessToken / refreshToken directly

### What's New in v1.6.2
- **Full Codex CLI support** - Uses the OpenAI Responses API (`/v1/responses`)
  - Full support for tool calls (shell, file, and all other tools)
  - Image input support (`input_image` type)
  - Web search support (`web_search` tool)
  - Error code mapping (`rate_limit`, `context_length`, etc.)
- **Enhanced Claude Code support** - Full image understanding and web search support
  - Supports both Anthropic and OpenAI image formats
  - Supports `web_search` / `web_search_20250305` tools

### What's New in v1.6.1
- **Request rate limiting** - Reduces account risk by controlling request frequency
  - Minimum interval per account
  - Maximum requests per minute per account
  - Global maximum requests per minute
  - Configurable in the Web UI settings page
- **Account anomaly detection** - Automatically detects errors such as `TEMPORARILY_SUSPENDED`
  - Clear and user-friendly error logs
  - Automatically disables affected accounts
  - Automatically switches to another available account
- **Unified error handling** - Shared error classification and handling logic across all three protocols

### Features in v1.6.0
- **Conversation history management** - Four strategies for handling context length limits, freely combinable
  - Auto truncation: preserve the most recent context and summarize earlier messages before sending; truncate by count / chars if necessary
  - Smart summarization: use AI to summarize earlier conversation while preserving key context
  - Summary cache: reuse recent summaries when history changes only slightly, reducing repeated LLM calls (enabled by default)
  - Retry on error: automatically truncate and retry on length errors (enabled by default)
  - Pre-check estimation: estimate token usage and truncate proactively before hitting the limit
- **Gemini tool-calling support** - Full support for `functionDeclarations` / `functionCall` / `functionResponse`
- **Settings page** - Added a settings tab in the Web UI for configuring conversation history management

### Features in v1.5.0
- **Usage tracking** - Check quota usage, including used / remaining / utilization rate
- **Multiple login methods** - Supports Google / GitHub / AWS Builder ID
- **Traffic monitoring** - Full LLM request monitoring with search, filtering, and export
- **Browser selection** - Automatically detects installed browsers and supports incognito mode
- **Documentation center** - Built-in help docs with sidebar navigation and Markdown rendering

### Features in v1.4.0
- **Token pre-refresh** - Background checks every 5 minutes and refreshes tokens 15 minutes before expiry
- **Health checks** - Verifies account availability every 10 minutes and updates status automatically
- **Enhanced request statistics** - Stats by account / model, plus 24-hour trends
- **Retry mechanism** - Automatic retry with exponential backoff for network errors / 5xx responses

## Tool Calling Support

| Feature | Anthropic (Claude Code) | OpenAI (Codex CLI) | Gemini |
|---------|--------------------------|--------------------|--------|
| Tool definitions | ✅ `tools` | ✅ `tools.function` | ✅ `functionDeclarations` |
| Tool call response | ✅ `tool_use` | ✅ `tool_calls` | ✅ `functionCall` |
| Tool result | ✅ `tool_result` | ✅ `tool` role message | ✅ `functionResponse` |
| Forced tool calling | ✅ `tool_choice` | ✅ `tool_choice` | ✅ `toolConfig.mode` |
| Tool count limit | ✅ 50 | ✅ 50 | ✅ 50 |
| History repair | ✅ | ✅ | ✅ |
| Image understanding | ✅ | ✅ | ❌ |
| Web search | ✅ | ✅ | ❌ |

## Known Limitations

### Conversation Length Limit

The Kiro API has an input length limit. When the conversation history becomes too long, it may return an error like:

```text
Input is too long. (CONTENT_LENGTH_EXCEEDS_THRESHOLD)
````

#### Automatic Handling (v1.6.0+)

The proxy includes built-in history management, configurable from the **Settings** page:

* **Retry on error** (default): automatically truncate and retry when a length error occurs
* **Smart summarization**: use AI to summarize earlier conversation while keeping key context
* **Summary cache** (default): reuse recent summaries when history changes only slightly, reducing repeated LLM calls
* **Auto truncation**: preserve the latest context and summarize earlier messages before each request; truncate by count / chars if needed
* **Pre-check estimation**: estimate token usage and truncate before hitting the limit

The summary cache can be tuned with the following config options (default values):

* `summary_cache_enabled`: `true`
* `summary_cache_min_delta_messages`: `3`
* `summary_cache_min_delta_chars`: `4000`
* `summary_cache_max_age_seconds`: `180`

#### Manual Handling

1. In Claude Code, enter `/clear` to clear the conversation history
2. Tell the AI what you were working on previously; it can read code files to recover context

## Quick Start

### Option 1: Download Prebuilt Release

Download the package for your platform from [Releases](../../releases), extract it, and run it directly.

### Option 2: Run from Source

```bash
# Clone the project
git clone https://github.com/yourname/kiro-proxy.git
cd kiro-proxy

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run
python run.py

# Or specify a port
python run.py 8081
```

After startup, visit:

```text
http://localhost:8080
```

### Command-Line Interface (CLI)

In headless environments, use the CLI to manage accounts and services:

```bash
# Account management
python run.py accounts list                 # List accounts
python run.py accounts export -o acc.json   # Export accounts
python run.py accounts import acc.json      # Import accounts
python run.py accounts add                  # Add token interactively
python run.py accounts scan --auto          # Scan and auto-add local tokens

# Login
python run.py login google                  # Google login
python run.py login github                  # GitHub login
python run.py login remote --host myserver.com:8080  # Generate remote login link

# Service
python run.py serve                         # Start service (default: 8080)
python run.py serve -p 8081                 # Specify port
python run.py status                        # Show status
```

### Getting Tokens

**Option 1: Online Login (Recommended)**

1. Open the Web UI and click **Online Login**
2. Choose a login method: Google / GitHub / AWS Builder ID
3. Complete authorization in the browser
4. The account will be added automatically

**Option 2: Scan Tokens**

1. Open Kiro IDE and sign in with a Google / GitHub account
2. After login, tokens are automatically saved to `~/.aws/sso/cache/`
3. Click **Scan Tokens** in the Web UI to add the account

## CLI Configuration

### Model Mapping

| Kiro Model          | Capability      | Claude Code         | Codex         |
| ------------------- | --------------- | ------------------- | ------------- |
| `claude-sonnet-4`   | ⭐⭐⭐ Recommended | `claude-sonnet-4`   | `gpt-4o`      |
| `claude-sonnet-4.5` | ⭐⭐⭐⭐ Stronger   | `claude-sonnet-4.5` | `gpt-4o`      |
| `claude-haiku-4.5`  | ⚡ Faster        | `claude-haiku-4.5`  | `gpt-4o-mini` |
| `claude-opus-4.5`   | ⭐⭐⭐⭐⭐ Best      | `claude-opus-4.5`   | `o1`          |

### Claude Code Configuration

```text
Name: Kiro Proxy
API Key: any
Base URL: http://localhost:8080
Model: claude-sonnet-4
```

### Codex Configuration

Codex CLI uses the OpenAI Responses API. Configure it like this:

```bash
# Set environment variables
export OPENAI_API_KEY=any
export OPENAI_BASE_URL=http://localhost:8080/v1

# Run Codex
codex
```

Or configure it in `~/.codex/config.toml`:

```toml
[providers.openai]
api_key = "any"
base_url = "http://localhost:8080/v1"
```

## API Endpoints

| Protocol  | Endpoint                                  | Purpose                   |
| --------- | ----------------------------------------- | ------------------------- |
| OpenAI    | `POST /v1/chat/completions`               | Chat Completions API      |
| OpenAI    | `POST /v1/responses`                      | Responses API (Codex CLI) |
| OpenAI    | `GET /v1/models`                          | Model list                |
| Anthropic | `POST /v1/messages`                       | Claude Code               |
| Anthropic | `POST /v1/messages/count_tokens`          | Token counting            |
| Gemini    | `POST /v1/models/{model}:generateContent` | Gemini CLI                |

### Admin API

| Endpoint                     | Method | Description                         |
| ---------------------------- | ------ | ----------------------------------- |
| `/api/accounts`              | GET    | Get all account states              |
| `/api/accounts/{id}`         | GET    | Get account details                 |
| `/api/accounts/{id}/usage`   | GET    | Get account usage info              |
| `/api/accounts/{id}/refresh` | POST   | Refresh account token               |
| `/api/accounts/{id}/restore` | POST   | Restore account from cooldown state |
| `/api/accounts/refresh-all`  | POST   | Refresh all soon-to-expire tokens   |
| `/api/flows`                 | GET    | Get traffic logs                    |
| `/api/flows/stats`           | GET    | Get traffic statistics              |
| `/api/flows/{id}`            | GET    | Get traffic detail                  |
| `/api/quota`                 | GET    | Get quota status                    |
| `/api/stats`                 | GET    | Get statistics                      |
| `/api/health-check`          | POST   | Trigger health check manually       |
| `/api/browsers`              | GET    | Get available browsers              |
| `/api/docs`                  | GET    | Get documentation list              |
| `/api/docs/{id}`             | GET    | Get documentation content           |

## Project Structure

```text
kiro_proxy/
├── main.py                    # FastAPI app entrypoint
├── config.py                  # Global configuration
├── converters.py              # Protocol conversion
│
├── core/                      # Core modules
│   ├── account.py            # Account management
│   ├── state.py              # Global state
│   ├── persistence.py        # Persistent config storage
│   ├── scheduler.py          # Background task scheduler
│   ├── stats.py              # Request statistics
│   ├── retry.py              # Retry mechanism
│   ├── browser.py            # Browser detection
│   ├── flow_monitor.py       # Traffic monitoring
│   └── usage.py              # Usage query
│
├── credential/                # Credential management
│   ├── types.py              # KiroCredentials
│   ├── fingerprint.py        # Machine ID generation
│   ├── quota.py              # Quota manager
│   └── refresher.py          # Token refresh
│
├── auth/                      # Authentication modules
│   └── device_flow.py        # Device Code Flow / Social Auth
│
├── handlers/                  # API handlers
│   ├── anthropic.py          # /v1/messages
│   ├── openai.py             # /v1/chat/completions
│   ├── responses.py          # /v1/responses (Codex CLI)
│   ├── gemini.py             # /v1/models/{model}:generateContent
│   └── admin.py              # Admin API
│
├── cli.py                     # Command-line interface
│
├── docs/                      # Built-in documentation
│   ├── 01-quickstart.md      # Quick start
│   ├── 02-features.md        # Features
│   ├── 03-faq.md             # FAQ
│   └── 04-api.md             # API reference
│
└── web/
    └── html.py               # Web UI (componentized single file)
```

## Build

```bash
# Install build dependency
pip install pyinstaller

# Build
python build.py
```

The output files will be generated in the `dist/` directory.

## Use Cases

* Connect Kiro-related capabilities to clients such as Claude Code, Codex CLI, and Gemini CLI
* Centralize request routing and account management in multi-account environments
* Maintain token refresh, quota status, and health checks in one place
* Provide a unified compatibility layer and observability surface for developer workflows

## Disclaimer

This project is for learning and research purposes only. Please use it in compliance with the applicable terms of service and relevant usage rules. Any consequences arising from the use of this project are the sole responsibility of the user.

This project is not officially affiliated with Kiro, AWS, Anthropic, Google or OpenAI.
