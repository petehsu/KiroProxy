# API Reference

## Proxy Endpoints

### OpenAI Protocol

#### POST /v1/chat/completions

Chat Completions API, OpenAI compatible.

**Request Example:**

```json
{
  "model": "gpt-4o",
  "messages": [
    {"role": "user", "content": "Hello!"}
  ],
  "stream": true
}
```

**Model Mapping:**

| Request Model | Actual Model |
|----------|----------|
| gpt-4o, gpt-4 | claude-sonnet-4 |
| gpt-4o-mini, gpt-3.5-turbo | claude-haiku-4.5 |
| o1, o1-preview | claude-opus-4.5 |

#### GET /v1/models

Get available models list.

---

### Anthropic Protocol

#### POST /v1/messages

Messages API, Anthropic compatible.

**Request Example:**

```json
{
  "model": "claude-sonnet-4",
  "max_tokens": 4096,
  "messages": [
    {"role": "user", "content": "Hello!"}
  ]
}
```

#### POST /v1/messages/count_tokens

Count message token count.

---

### Gemini Protocol

#### POST /v1/models/{model}:generateContent

Generate Content API, Gemini compatible.

---

## Management API

### Status & Statistics

| Endpoint | Method | Description |
|------|------|------|
| `/api/status` | GET | Service status |
| `/api/stats` | GET | Basic statistics |
| `/api/stats/detailed` | GET | Detailed statistics |
| `/api/quota` | GET | Quota status |
| `/api/logs` | GET | Request logs |

### Account Management

| Endpoint | Method | Description |
|------|------|------|
| `/api/accounts` | GET | Account list |
| `/api/accounts` | POST | Add account |
| `/api/accounts/{id}` | GET | Account details |
| `/api/accounts/{id}` | DELETE | Delete account |
| `/api/accounts/{id}/toggle` | POST | Enable/disable |
| `/api/accounts/{id}/refresh` | POST | Refresh Token |
| `/api/accounts/{id}/restore` | POST | Restore account |
| `/api/accounts/{id}/usage` | GET | Usage query |
| `/api/accounts/refresh-all` | POST | Refresh all |

### Token Operations

| Endpoint | Method | Description |
|------|------|------|
| `/api/token/scan` | GET | Scan local Tokens |
| `/api/token/add-from-scan` | POST | Add from scan |
| `/api/token/refresh-check` | POST | Check Token status |

### Login

| Endpoint | Method | Description |
|------|------|------|
| `/api/kiro/login/start` | POST | Start AWS login |
| `/api/kiro/login/poll` | GET | Poll login status |
| `/api/kiro/login/cancel` | POST | Cancel login |
| `/api/kiro/social/start` | POST | Start Social login |
| `/api/kiro/social/exchange` | POST | Exchange Token |

### Flow Monitoring

| Endpoint | Method | Description |
|------|------|------|
| `/api/flows` | GET | Query Flows |
| `/api/flows/stats` | GET | Flow statistics |
| `/api/flows/{id}` | GET | Flow details |
| `/api/flows/{id}/bookmark` | POST | Bookmark Flow |
| `/api/flows/export` | POST | Export Flows |

---

## Configuration

### Config File Locations

- Account config: `~/.kiro-proxy/config.json`
- Token cache: `~/.aws/sso/cache/`

### Config Import/Export

| Endpoint | Method | Description |
|------|------|------|
| `/api/config/export` | GET | Export config |
| `/api/config/import` | POST | Import config |
