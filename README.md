<div align="center">

# 🌉 Antigravity Bridge

**Turn Google's free Antigravity IDE into a REST API — access Claude Opus 4.6, Gemini 3.1 Pro, and more for free**

Antigravity Bridge is an unofficial Python tool that connects to the [Google Antigravity](https://antigravity.google) desktop app on macOS through the Chrome DevTools Protocol (CDP) and exposes its chat as a local REST API, so your own scripts and agents can send prompts to the models available in Antigravity — for personal research only.

中文：非官方工具，通过 CDP 把 macOS 上的 Google Antigravity 桌面端聊天变成本地 REST API，方便自己的脚本 / AI agent 调用；仅供个人研究，违反服务条款，有封号风险。

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

**Antigravity Bridge** wraps [Antigravity](https://antigravity.google) — Google's AI desktop app — into a local REST API via Chrome DevTools Protocol (CDP). One endpoint for the models listed in Antigravity's UI.

## 🚀 Quick Start

### 1. Install & Start

```bash
# Install Antigravity from https://antigravity.google
# The scripts here target macOS (tested on Apple Silicon, per `language_server_macos_arm`)

git clone https://github.com/ythx-101/antigravity-bridge.git
cd antigravity-bridge
pip install -r requirements.txt   # equivalent: pip install websockets
```

Pick **one** of the two ways to start (don't run both — the port would already be in use):

```bash
# Option A: one script starts Antigravity (CDP on 9229) AND the bridge (log: /tmp/ag_bridge.log)
bash scripts/start_antigravity.sh

# Option B: manual
open -a Antigravity --args --remote-debugging-port=9229
python3 scripts/bridge.py
```

### 2. Use the API

```bash
# Chat with Opus
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

1. **Antigravity** is launched with `--remote-debugging-port=9229` (`start_antigravity.sh` does this via `open -a Antigravity --args ...`, or run that command yourself)
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

## 💻 CLI helper (`ag`)

`scripts/ag_chat.sh` prints a plain-text reply. Set it up as an alias:

```bash
alias ag="bash $(pwd)/scripts/ag_chat.sh"
ag "Your question" [model] [timeout]     # model defaults to opus, timeout to 180s
```

Model shorthands: `opus`, `sonnet`, `gemini`, `gemini-low`, `flash`, `gpt` (any other value is passed through as the full model name). It retries up to 3 times on high traffic.

To reach a bridge on another machine, set the full URL: `AG_BRIDGE_HOST=http://<mac-ip>:19999 ag "hi"`.

## 🧑‍💻 IDE Agent mode (`agy_invoke.sh`)

`bash scripts/agy_invoke.sh "Task description" [--model opus|gemini|sonnet|flash]` triggers the Antigravity IDE agent over SSH + CDP. It needs SSH (Remote Login) access to the Mac, and Node.js with the `ws` package on the Mac. Configure with `MAC_SSH_HOST`, `MAC_SSH_USER`, `MAC_SSH_PORT`, `AGY_NODE_PATH` (env vars or `~/.remote-mac.conf`); see the header of the script.

## ⚖️ When to use / When not to use

| | Antigravity Bridge | Official APIs (Anthropic / Google Gemini API) |
|---|---|---|
| Officially supported | No | Yes |
| Complies with ToS | No — may get your account banned | Yes |
| Stability | Can break any time (depends on Antigravity's DOM and quota) | Versioned, documented |
| Production / multi-user | No | Yes |
| Cost model | Relies on Antigravity's own free quota, which can change at any time | Pay-as-you-go |

Use the bridge for personal experiments with a throwaway account. For anything else, use the official APIs.

## ❓ FAQ

### Will my Google account get banned? / 会被封号吗？
There is a real risk — see the Risk Warning (CAUTION block) at the top of this README and [Issue #1](https://github.com/ythx-101/antigravity-bridge/issues/1). Use a throwaway account, never your primary one, and add delays between requests.

### Does it work on Windows / Linux? / 能在 Windows / Linux 上用吗？
The scripts target macOS only (`open -a`, `osascript`, `language_server_macos_arm`). Other platforms are untested.

### Messages are sent but I never get a reply / 消息发出去但没有回复
See "Messages send but no response" under Known Issues (self-signed cert, fixed in v1.3.0) and make sure your network can reach `googleapis.com`.

### Port 19999 is already in use / 端口 19999 被占用
`start_antigravity.sh` already starts a bridge in the background. Use Option A *or* Option B, not both.

### Which models are available? / 有哪些模型可用？
Whatever Antigravity shows in its UI. The `MODELS` list in `bridge.py` is hard-coded and may be outdated; `GET /models` shows it.

### Is it OpenAI API compatible? / 兼容 OpenAI API 吗？
No. It uses custom endpoints, see API Reference.

### Can I call it from another machine? / 能从另一台机器调用吗？
Yes — the bridge listens on `0.0.0.0` (use `AG_BRIDGE_HOST` with `ag`). **There is no authentication**, so only do this on a trusted network.

### Production or multi-user use? / 能用于生产或多用户吗？
No.

## 📁 Files

```
antigravity-bridge/
├── README.md
├── CHANGELOG.md
├── LICENSE
├── SKILL.md
├── llms.txt                  # Summary for LLMs
├── requirements.txt          # websockets>=10
├── tests/test_bridge.py      # Offline tests (no Antigravity needed)
└── scripts/
    ├── bridge.py             # REST API server
    ├── start_antigravity.sh  # Starts Antigravity with CDP and the bridge
    ├── ag_chat.sh            # `ag` CLI helper
    ├── agy_invoke.sh         # Trigger the IDE agent over SSH + CDP
    └── cdp_inject.js         # Node.js CDP injection script used by agy_invoke.sh
```

Run the tests: `python3 -m unittest discover -s tests`

## 📝 Requirements

- macOS with [Antigravity](https://antigravity.google) installed
- Python 3.8+ with `websockets` package (`requirements.txt`)
- Network access to `googleapis.com`

## License

MIT
