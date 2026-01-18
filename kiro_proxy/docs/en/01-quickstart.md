# Quick Start

## Installation

### Option 1: Download Pre-built Binary

Download the package for your platform from [Releases](https://github.com/petehsu/KiroProxy/releases):

- **Windows**: `kiro-proxy-windows.zip`
- **macOS**: `kiro-proxy-macos.zip`
- **Linux**: `kiro-proxy-linux.tar.gz`

Extract and double-click to run.

### Option 2: Run from Source

```bash
# Clone the project
git clone https://github.com/petehsu/KiroProxy.git
cd KiroProxy

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run (default port 8080)
python run.py

# Specify port
python run.py 8081
```

After startup, open http://localhost:8080 in your browser.

---

## Get Kiro Account

Kiro Proxy needs Kiro account tokens to work. Two ways to get them:

### Option 1: Online Login (Recommended)

1. Open Web UI, click "Accounts" tab
2. Click "Online Login" button
3. Choose login method:
   - **Google** - Use Google account
   - **GitHub** - Use GitHub account
   - **AWS** - Use AWS Builder ID
4. Complete authorization in the browser popup
5. Account is automatically added to the proxy

### Option 2: Scan Local Tokens

If you've already logged into Kiro IDE:

1. Open Kiro IDE, make sure you're logged in
2. Return to Web UI, click "Scan Tokens"
3. System scans `~/.aws/sso/cache/` directory
4. Select token files to add

---

## Configure AI Client

### Claude Code (VSCode Plugin)

This is the recommended method. Tool calling has been verified to work.

1. Install Claude Code plugin
2. Open settings, add custom Provider:

```
Name: Kiro Proxy
API Provider: Anthropic
API Key: any (any value works)
Base URL: http://localhost:8080
Model: claude-sonnet-4
```

3. Select Kiro Proxy as current Provider

### Codex CLI

OpenAI official command line tool.

```bash
# Install
npm install -g @openai/codex

# Configure (~/.codex/config.toml)
model = "gpt-4o"
model_provider = "kiro"

[model_providers.kiro]
name = "Kiro Proxy"
base_url = "http://localhost:8080/v1"
```

### Other Compatible Clients

Any client supporting OpenAI or Anthropic API can be used:

- **Base URL**: `http://localhost:8080` or `http://localhost:8080/v1`
- **API Key**: Any value (proxy doesn't verify)
- **Model**: See model mapping table below

---

## Model Mapping

| Kiro Model | Capability | Available Names |
|-----------|------|---------------------|
| `claude-sonnet-4` | ⭐⭐⭐ Recommended | `gpt-4o`, `gpt-4`, `sonnet` |
| `claude-sonnet-4.5` | ⭐⭐⭐⭐ Stronger | `gemini-1.5-pro` |
| `claude-haiku-4.5` | ⚡ Fast | `gpt-4o-mini`, `gpt-3.5-turbo`, `haiku` |
| `claude-opus-4.5` | ⭐⭐⭐⭐⭐ Strongest | `o1`, `o1-preview`, `opus` |
| `auto` | 🤖 Auto | `auto` |

> 💡 **Tip**: Not sure which model to use? Just use `claude-sonnet-4` or `gpt-4o`, best value for money.
