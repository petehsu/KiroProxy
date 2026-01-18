# Features

## Multi-Protocol Support

Kiro Proxy supports three major AI API protocols:

| Protocol | Endpoint | Compatible Clients |
|------|------|------------|
| OpenAI | `/v1/chat/completions` | Codex CLI, ChatGPT clients |
| Anthropic | `/v1/messages` | Claude Code, Claude clients |
| Gemini | `/v1/models/{model}:generateContent` | Gemini CLI |

The proxy automatically converts requests to Kiro API format and responses back to the corresponding protocol format.

---

## Tool Calling Support

Full support for tool calling in all three protocols:

### Anthropic Protocol (Claude Code)

- `tools` definition and `tool_result` response fully supported
- `tool_choice: required` support (via prompt injection)
- `web_search` special tool auto-recognized
- Tool count limit (max 50)
- Description truncation (auto-truncate over 500 characters)

### OpenAI Protocol (Codex CLI)

- `tools` definition (function type)
- `tool_calls` response processing
- `tool` role message conversion
- `tool_choice: required/any` support

### History Message Repair

Kiro API requires messages to strictly alternate (user → assistant → user → assistant). The proxy automatically:

- Detects and fixes consecutive same-role messages
- Merges duplicate tool_results
- Inserts placeholder messages to maintain alternation

---

## Multi-Account Management

### Account Rotation

Add multiple Kiro accounts, proxy automatically rotates:

- Each request selects an available account
- Automatically skips cooldown or unhealthy accounts
- Load balancing to avoid single account pressure

### Session Stickiness

To maintain conversation context continuity:

- Same session ID uses same account within 60 seconds
- Switches only after 60 seconds or if account unavailable

### Account States

Each account has four states:

| State | Description | Color |
|------|------|------|
| Active | Normal, available | Green |
| Cooldown | Rate limited, cooling down | Yellow |
| Unhealthy | Health check failed | Red |
| Disabled | Manually disabled | Gray |

---

## Token Auto-Refresh

### Auto Detection

- Background checks all account Tokens every 5 minutes
- Detects Tokens expiring within 15 minutes

### Auto Refresh

- Automatically refreshes expiring Tokens
- Supports Social auth (Google/GitHub) refresh_token
- Failed refresh marks account as unhealthy

### Manual Refresh

- Click "Refresh Token" on account card
- Or click "Refresh All Tokens" for batch refresh

---

## Quota Management

### 429 Auto-Handling

When Kiro API returns 429 (Too Many Requests):

1. Automatically marks account as Cooldown
2. Sets 5-minute cooldown time
3. Immediately switches to other available accounts for retry
4. Auto-recovers after cooldown ends

### Manual Recovery

To recover account early:

1. Check quota status on "Monitor" page
2. Click "Restore" button next to account

---

## History Message Management

### Conversation Length Limit

Kiro API has input length limits. When conversation history is too long, it returns `CONTENT_LENGTH_EXCEEDS_THRESHOLD` error.

Proxy has built-in strategies to handle this:

### Available Strategies

| Strategy | Description | Trigger |
|------|------|----------|
| Auto Truncate | Prioritize recent context, truncate if needed | Before each request |
| Smart Summary | Use AI to generate early conversation summary | When threshold exceeded |
| Error Retry | Truncate and retry on length error | After receiving error |
| Pre-estimate | Estimate token count, pre-truncate if exceeds | Before each request |

### Recommended Configuration

- **Default**: Enable only "Error Retry", auto-handles issues
- **Conservative**: Enable "Smart Summary + Error Retry", preserve key info
- **Aggressive**: Enable "Auto Truncate + Pre-estimate", preventive truncation

---

## Configuration Persistence

### Auto Save

Account configuration auto-saves to `~/.kiro-proxy/config.json`:

- Account list and states
- Enable/disable settings
- Token file paths

### Restart Recovery

After restart, automatically loads saved configuration, no need to re-add accounts.

### Import/Export

- "Export Config" downloads current configuration
- "Import Config" restores from file
