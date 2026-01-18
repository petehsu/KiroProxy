# FAQ

## Connection Issues

### Cannot Connect to Proxy

**Symptoms**: Client reports `Connection refused` or `ECONNREFUSED`

**Solutions**:

1. Confirm proxy is running
   ```bash
   python run.py
   # Should see: Kiro API Proxy v1.7.1
   #             http://localhost:8080
   ```

2. Check port is correct
   - Default port is 8080
   - If port changed, update client config too

3. Check firewall
   - Windows: Allow Python through firewall
   - macOS: System Preferences → Security & Privacy → Firewall

### 401 Authentication Failed

**Symptoms**: Request returns 401 Unauthorized

**Cause**: Token expired or invalid

**Solutions**:

1. Click "Refresh Token" on account card
2. If refresh fails, re-login to get new Token
3. Check account status is Active

---

## Request Issues

### 429 Too Many Requests

**Symptoms**: Request returns 429 error

**Cause**: Kiro has request rate limits

**Proxy auto-handling**:

- Cools down account for 5 minutes
- Auto-switches to other available accounts
- Auto-recovers after cooldown ends

**Suggestions**:

- Add multiple accounts to distribute requests
- Avoid too many requests in short time
- Check quota status on "Monitor" page

### Conversation Too Long (CONTENT_LENGTH_EXCEEDS_THRESHOLD)

**Symptoms**: Request returns `Input is too long` error

**Cause**: Kiro API has input length limits

**Proxy auto-handling**:

Built-in history message management, configurable in "Settings":

1. **Auto Truncate** - Prioritize recent context, truncate if needed
2. **Error Retry** - Auto truncate and retry on length error (default enabled)
3. **Pre-estimate** - Estimate token count, pre-truncate if exceeds

Recommended: **Error Retry** (default) or **Auto Truncate + Pre-estimate**

**Manual solution**:

1. In Claude Code, type `/clear` to clear conversation history
2. After clearing, tell AI what you were working on
3. AI will read code files to restore context

---

## Token Issues

### Token Expired

**Auto handling**: Proxy auto-detects and refreshes Tokens

**Manual handling**:

1. Click "Refresh Token" button on account card
2. If refresh fails, refresh_token is also expired
3. Need to re-login for new Token

### How to Add Multiple Accounts

**Method 1: Multiple Online Logins**

1. Use different Google/GitHub accounts
2. Each login auto-adds new account

**Method 2: Scan Tokens**

1. Login with different accounts in Kiro IDE
2. Click "Scan Tokens" after each login
3. Select new Token files to add

### Where are Token Files

Tokens are saved in `~/.aws/sso/cache/`:

```
~/.aws/sso/cache/
├── xxxxxxxx.json  # Token file
├── yyyyyyyy.json  # Another Token
└── ...
```

---

## Model Issues

### Supported Models

| Model | Capability | Recommended Use |
|------|------|----------|
| claude-sonnet-4 | ⭐⭐⭐ Balanced | Daily programming, recommended |
| claude-sonnet-4.5 | ⭐⭐⭐⭐ Stronger | Complex tasks |
| claude-haiku-4.5 | ⚡ Fast | Simple Q&A, speed-first |
| claude-opus-4.5 | ⭐⭐⭐⭐⭐ Strongest | Highest quality requirements |

### Model Mapping

OpenAI model names auto-map:

| Request Model | Actual Model |
|----------|----------|
| gpt-4o, gpt-4 | claude-sonnet-4 |
| gpt-4o-mini, gpt-3.5-turbo | claude-haiku-4.5 |
| o1, o1-preview | claude-opus-4.5 |

### Tool Calling Support

**Yes!** Claude Code tool calling is verified to work, including:

- File read/write
- Command execution
- Code search
- And more

---

## Other Issues

### How to View Request Logs

1. Open "Logs" tab
2. View recent request records
3. Includes time, path, model, status, duration

### How to Monitor Account Status

1. Open "Monitor" tab
2. View service status and statistics
3. View quota status and cooldown accounts

### Where are Config Files

- Account config: `~/.kiro-proxy/config.json`
- Token files: `~/.aws/sso/cache/*.json`
