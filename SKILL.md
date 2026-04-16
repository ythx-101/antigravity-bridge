---
name: antigravity-bridge
description: "Expose the Antigravity AI desktop app as a local REST API via Chrome DevTools Protocol (CDP). Use when the user needs to send prompts to Antigravity-hosted models (Claude Opus 4.6, Gemini 3.1 Pro, Claude Sonnet 4.6, Gemini 3 Flash, GPT-OSS 120B) programmatically, integrate Antigravity into scripts or agents, or troubleshoot the CDP bridge connection."
---

# Antigravity Bridge

Turn the Antigravity desktop app into a local REST API by injecting commands through Chrome DevTools Protocol (CDP). Supports synchronous chat, async tasks, model switching, and conversation management across six free AI models.

## Setup

1. Install [Antigravity](https://antigravity.com) (macOS only)
2. Start Antigravity with CDP enabled:
   ```bash
   bash scripts/start_antigravity.sh
   ```
3. Start the bridge server:
   ```bash
   python3 scripts/bridge.py
   ```
4. Verify the connection:
   ```bash
   curl -s http://localhost:19999/health
   # Expected: {"status":"ok", ...}
   ```

## Usage

### Mode 1: Bridge API (Q&A)

```bash
# CLI shortcut (uses ag_chat.sh)
ag "Your question" [opus|gemini|sonnet|flash|gpt] [timeout]

# Direct HTTP call
curl -s -X POST http://localhost:19999/chat \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Explain quantum computing","model":"Claude Opus 4.6 (Thinking)"}'

# Async mode for long tasks
curl -s -X POST http://localhost:19999/async \
  -d '{"prompt":"Deep analysis...","timeout":600}'
# Poll result:
curl -s http://localhost:19999/task/<task_id>
```

### Mode 2: IDE Agent (project tasks)

```bash
bash scripts/agy_invoke.sh "Fix the login bug" --model sonnet
```

## Parameters

- `model`: `opus` (Claude Opus 4.6), `gemini` (Gemini 3.1 Pro), `sonnet` (Claude Sonnet 4.6), `flash` (Gemini 3 Flash), `gpt` (GPT-OSS 120B)
- `timeout`: seconds to wait for response (default: 180)

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/chat` | Synchronous chat |
| POST | `/async` | Async chat, returns `task_id` |
| GET | `/task/{id}` | Poll async task result |
| POST | `/new` | Start new conversation |
| POST | `/model` | Switch active model |
| GET | `/health` | Connection health check |
| GET | `/models` | List available models |

## Key Files

- `scripts/bridge.py` — REST API server, CDP WebSocket connection, async task management
- `scripts/start_antigravity.sh` — Launches Antigravity with `--remote-debugging-port=9229`
- `scripts/ag_chat.sh` — CLI wrapper with auto-retry on high traffic
- `scripts/agy_invoke.sh` — IDE agent mode for project-scoped tasks
- `scripts/cdp_inject.js` — CDP injection helpers

## Configuration

- Bridge port: `--port` (default: 19999)
- CDP port: `--cdp-port` (default: 9229)
- Host: `localhost` (or set `AG_BRIDGE_HOST` env var)

## Troubleshooting

- **No response after sending message**: The SSL cert fix (`Security.setIgnoreCertificateErrors`) is applied automatically in v1.3.0+. Ensure bridge.py is up to date.
- **"No Antigravity" error**: Antigravity must be running with CDP enabled on port 9229. Re-run `scripts/start_antigravity.sh`.
- **gRPC connection fails**: Ensure network access to `googleapis.com` is not blocked by a firewall.
