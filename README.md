<div align="center">

# 🌉 Antigravity Bridge

**Turn Google's free Antigravity IDE into a REST API — access Claude Opus 4.6, Gemini 3.1 Pro, and more for free**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![Version](https://img.shields.io/badge/Version-1.3.1-green.svg)](CHANGELOG.md)

*6 free AI models · REST API · Sync & async chat · Image generation*

</div>

---

> [!CAUTION]
> **⚠️ Risk Warning — Read Before Use**
>
> This project turns a desktop client into a headless API via CDP injection. This **violates Antigravity's Terms of Service** and carries real risks:
>
> - **Account throttling** — Rate limits, degraded responses, shadow-banning
> - **Account ban** — Your Google account may be suspended, potentially affecting other Google services (GCP, Workspace, Gmail)
> - **Detection is trivial** — CDP debugger attachment, `Security.setIgnoreCertificateErrors`, and non-human interaction patterns (zero typing delay, no cursor movement) are all easily detectable
>
> **Protect yourself:**
> 1. 🚫 **Never use your primary Google account** — Register a throwaway account
> 2. 🐢 **Add delays between requests** — Mimic human typing speed, avoid high concurrency
> 3. 🧪 **Personal research only** — Do not use as a production API or multi-user backend
> 4. 💀 **Expect breakage** — This is a cat-and-mouse game; the channel can be killed at any time
>
> *Use at your own risk. The authors are not responsible for any account actions taken by Google/Antigravity.*

---

## 😡 The Problem

> "Opus 4.6 API costs hundreds per month"
> "Gemini 3.1 Pro is free but has no convenient API"
> "I want my agent to use multiple models without paying for each"

**Antigravity Bridge** wraps [Antigravity](https://antigravity.com) — a free AI desktop app by Google — into a standard REST API via Chrome DevTools Protocol (CDP). One endpoint, six free models.

## 🚀 Quick Start

### 1. Install & Start

```bash
# Install Antigravity from https://antigravity.com
# macOS: app bundle
# Linux: install the desktop package so the `antigravity` launcher is on PATH

# Clone this repo
git clone https://github.com/ythx-101/antigravity-bridge.git
cd antigravity-bridge

# Install dependency
pip install websockets

# Start Antigravity with CDP
bash scripts/start_antigravity.sh

# Start the bridge
python3 scripts/bridge.py
```

### 2. Use the API

```bash
# Chat with Opus (free!)
curl -X POST http://localhost:19999/chat \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Explain quantum computing","model":"Claude Opus 4.6 (Thinking)"}'

# Async mode (recommended for long tasks)
curl -X POST http://localhost:19999/async \
  -d '{"prompt":"Deep analysis...","timeout":600}'
# → {"status":"accepted","task_id":"abc123"}
curl http://localhost:19999/task/abc123

# New conversation (clear context)
curl -X POST http://localhost:19999/new

# Health check
curl http://localhost:19999/health
```

## 🤖 Available Models

| Model | Key | Best For |
|-------|-----|----------|
| Claude Opus 4.6 (Thinking) | `Claude Opus 4.6 (Thinking)` | Deep reasoning |
| Gemini 3.1 Pro (High) | `Gemini 3.1 Pro (High)` | Fast + image gen |
| Claude Sonnet 4.6 (Thinking) | `Claude Sonnet 4.6 (Thinking)` | Balanced |
| Gemini 3 Flash | `Gemini 3 Flash` | Fastest |
| GPT-OSS 120B (Medium) | `GPT-OSS 120B (Medium)` | GPT alternative |
| Gemini 3.1 Pro (Low) | `Gemini 3.1 Pro (Low)` | Quota-friendly |

## 📡 API Reference

| Method | Path | Description |
|--------|------|-------------|
| POST | `/chat` | Synchronous chat (default 180s timeout) |
| POST | `/async` | Async chat, returns `task_id` |
| GET | `/task/{id}` | Poll async result |
| POST | `/new` | New conversation (two-phase reload) |
| POST | `/model` | Switch model |
| GET | `/health` | Health check |
| GET | `/models` | List available models |
| GET | `/history` | Current conversation content |
| GET | `/imgcount` | Count generated images |
| GET | `/extract?after=N` | Extract generated image as base64 |

## 📊 Architecture

```
Your Agent / Script
    │
    ├── curl http://localhost:19999/chat
    │
    └── bridge.py (:19999)
          │ WebSocket (CDP)
          ▼
        Antigravity (CDP :9229)
          │ Security.setIgnoreCertificateErrors ← v1.3.0 fix
          ▼
        language_server_macos_arm
          │ gRPC over TLS
          ▼
        googleapis.com (AI models)
```

## 🔧 How It Works

1. **Antigravity** runs with `--remote-debugging-port=9229` (auto-configured via `argv.json`)
2. **bridge.py** connects via CDP WebSocket to the Antigravity chat UI
3. Messages are injected into the Lexical editor via `document.execCommand('insertText')`
4. Responses are polled from the DOM until completion markers appear
5. **SSL Fix**: Antigravity's `language_server` uses a self-signed cert (`CN=localhost`). The bridge calls `Security.setIgnoreCertificateErrors` to allow the renderer's `fetch()` to communicate with it

## ⚠️ Known Issues & Solutions

### "Messages send but no response" (most common)
**Root cause**: Electron's `fetch()` rejects the self-signed SSL cert used by `language_server_macos_arm`.

**Fix** (applied in v1.3.0): The bridge automatically calls `Security.setIgnoreCertificateErrors({ignore: true})` before each chat.

### "gRPC connection fails"
The `language_server` connects to `daily-cloudcode-pa.googleapis.com` via gRPC. If this endpoint is unreachable (e.g., blocked by firewall), models will show as placeholders and won't respond.

**Fix**: Ensure your network can reach `googleapis.com`.

### Planning mode gets stuck
Some long prompts trigger Antigravity's "Planning" mode which can hang.

**Fix**: The bridge auto-switches to "Fast" mode. Keep prompts concise.

## 📁 Files

```
antigravity-bridge/
├── README.md
├── CHANGELOG.md
├── LICENSE
├── SKILL.md
└── scripts/
    ├── bridge.py             # REST API server (v1.3.0)
    └── start_antigravity.sh  # macOS/Linux startup helper
```

## 📝 Requirements

- macOS or Linux with [Antigravity](https://antigravity.com) installed
- Python 3.8+ with `websockets` package
- Network access to `googleapis.com`

## License

MIT
