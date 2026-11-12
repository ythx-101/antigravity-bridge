# Changelog

## [Unreleased]

### Fixes
- `bridge.py`: empty POST body (e.g. `curl -X POST /new`) no longer drops the connection; invalid JSON returns 400; `GET /extract?after=x` returns 400
- `start_antigravity.sh`: remove stray `killall mitmdump`; fix `pkill` pattern so the old bridge is actually stopped (uses `$BRIDGE_PORT`)

### Added
- `requirements.txt` (`websockets>=10`)
- `tests/test_bridge.py`: offline unittest suite
- `llms.txt`

### Documentation
- README: one-line description (EN/中文), correct Antigravity URL (`antigravity.google`), fixed Quick Start (start script already launches the bridge), `ag` and `agy_invoke.sh` sections, comparison table, FAQ, complete file list
- SKILL.md: `ag` alias, `gemini-low`, `AG_BRIDGE_HOST` takes a full URL, risk note

## [1.3.1] - 2026-03-09

### Documentation
- Add prominent risk warning (CAUTION block) to README — account ban risks, detection methods, safety guidelines
- Respond to community question about account safety (Issue #1)

### Notes
- Model switching logic confirmed working in bridge.py
- The model selector uses DOM inspection: click span.select-none.min-w-0 parent to open dropdown, find model name, click

## [1.3.0] - 2026-03-09

### Critical Fix: SSL Certificate
- Fix Electron `fetch()` rejecting `language_server`'s self-signed SSL cert (`CN=localhost`)
- Root cause: Google's language server uses HTTPS with a self-signed cert for localhost IPC; Chromium's security policy rejects it silently, causing messages to send but never reach the model
- Fix: `Security.setIgnoreCertificateErrors({ignore: true})` called via CDP before each chat

### Bug Fixes  
- Fix `/new` (reload) breaking subsequent chat — two-phase reload: trigger on old connection → wait → reconnect to new page
- Fix WebSocket Origin header rejected by Electron — remove Origin param entirely (Electron accepts no-Origin connections)
- Fix Lexical editor state corruption — use `execCommand('selectAll') + execCommand('delete')` instead of `textContent = ''`
- Fix Launchpad page (`workbench-jetski-agent.html`) being selected as target — filter by URL pattern
- Auto-switch to "Fast" mode to prevent Planning mode hangs

### New Features
- `_ssl_fix()` extracted as reusable method
- Two-phase reload with retry (up to 5 attempts)
- `data-lexical-editor` fallback selector for textbox detection

## [1.2.0] - 2026-03-06

### New Features
- Async chat mode: POST `/async` returns `task_id`, poll with GET `/task/{id}`
- No more client-side timeouts for long-running queries

## [1.1.0] - 2026-03-05

### New Features
- Self-healing bridge with CDP watchdog (auto-reconnect on disconnect)
- Retry with exponential backoff on chat failures

## [1.0.0] - 2026-03-04

### Initial Release
- CDP bridge for Antigravity as REST API
- Multi-model support (Opus 4.6 / Gemini 3.1 Pro / Flash / Sonnet 4.6 / GPT-OSS)
- Sync chat, model switching, health check
- IDE Agent mode via CDP injection
