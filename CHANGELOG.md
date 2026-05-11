# Changelog

## v1.8.1 - 2026-05-11

### Per-account proxy
- Added `proxy_url` field to Account, allowing each account to use a separate HTTP/SOCKS5 proxy.
- Account proxy takes priority over the global `KIRO_VPN_PROXY_URL`; empty falls back to global or direct.
- All outbound paths use account proxy: Kiro API calls, token refresh, health checks, usage queries.
- New API endpoint: `PUT /api/accounts/{id}/proxy` for updating proxy per account.
- Web UI: inline proxy display and edit per account card.
- i18n: Chinese and English translations for proxy UI strings.

## v1.8.0 - 2026-05-10

### Comprehensive upgrade (15 optimizations)
- Dynamic model resolution (4-layer pipeline).
- Payload size guard (615KB limit detection + auto-trimming).
- Truncation recovery (detect truncated responses + inject synthetic messages).
- Global VPN/Proxy support (HTTP/SOCKS5 via `KIRO_VPN_PROXY_URL`).
- loguru structured logging (levels, file output, debug mode).
- `.env` configuration via python-dotenv.
- Docker deployment (Dockerfile + docker-compose).
- tiktoken token counting (replaces rough `len/4` estimation).
- Extended Thinking FSM parser.
- kiro-cli SQLite auth integration.
- Prompt Caching (cache_control → cachePoint).
- Tool Search (regex + BM25).
- Circuit Breaker (exponential backoff + probabilistic retry).
- Pydantic data validation models.
- Comprehensive type hints and docstrings.

## v1.7.17 - 2026-04-18

### Core fixes
- Fixed Kiro upstream `profileArn is required` failures by enforcing top-level `profileArn` in outbound Kiro requests.
- Added auth guard and recovery flow for missing `profileArn` (refresh, env/log backfill, clear diagnostics).
- Improved credential loading resilience with cache-directory JSON merge and corrupted JSON field recovery.
- Stabilized machine fingerprint generation (`uuid > profileArn > clientId > system id`) to reduce multi-account jitter.

### Protocol compatibility
- Deepened Anthropic/OpenAI/Responses/Gemini conversion compatibility for current CLI behaviors.
- Added stronger history/tool pairing normalization to reduce protocol drift regressions.
- Added thinking-prefix mapping support for Anthropic/OpenAI/Gemini request variants.
- Expanded tool description handling for long tool schemas used by external clients.

### Regression testing
- Added end-to-end fixture regression tests for:
  - Claude Code (`/v1/messages`)
  - Codex Responses API (`/v1/responses`)
  - Gemini CLI (`/v1/models/*:generateContent`)
- Added real flow fixture regression coverage to lock `profileArn` auth-error classification behavior.
- Added credential merge/corruption recovery tests and machine-id stability tests.
