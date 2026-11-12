---
name: antigravity-bridge
description: Call models inside the Google Antigravity desktop app from scripts via a local CDP-based REST API (macOS, unofficial)
---

# Antigravity Bridge

Turn Antigravity (free AI desktop app) into a REST API via Chrome DevTools Protocol (CDP).

> ⚠️ Unofficial; violates Antigravity's ToS and may get your account banned. Personal research only, use a throwaway account. See the CAUTION block in [README.md](README.md).

## Usage

### Mode 1: Bridge API (Q&A)
```bash
# CLI (ag is an alias for scripts/ag_chat.sh)
alias ag="bash $(pwd)/scripts/ag_chat.sh"
ag "Your question" [model] [timeout]

# HTTP
curl -s -X POST http://localhost:19999/chat \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Your question","model":"Claude Opus 4.6 (Thinking)"}'
```

### Mode 2: IDE Agent (project tasks)
```bash
bash scripts/agy_invoke.sh "Task description" [--model opus]
```

## Parameters
- `model`: `opus` (Claude Opus 4.6), `gemini` (Gemini 3.1 Pro High), `gemini-low` (Gemini 3.1 Pro Low), `sonnet` (Claude Sonnet 4.6), `flash` (Gemini 3 Flash), `gpt` (GPT-OSS 120B)

## Examples
```bash
# Health check
curl -s http://localhost:19999/health

# Call Claude Opus
ag "Write a bash script" opus

# IDE agent task
bash scripts/agy_invoke.sh "Fix bug in common.sh" --model sonnet
```

## Requirements
- Mac with Antigravity installed and running
- Antigravity started with `--remote-debugging-port=9229`
- Bridge mode: `pip install -r requirements.txt`, then run `bash scripts/start_antigravity.sh` (starts both) or `python3 scripts/bridge.py`
- IDE mode: Node.js with `ws` package

## Configuration
- Bridge port: `--port` (default: 19999)
- CDP port: `--cdp-port` (default: 9229)
- Bridge URL for `ag`: `AG_BRIDGE_HOST` must be a full URL, e.g. `http://<mac-ip>:19999` (default `http://localhost:19999`)
