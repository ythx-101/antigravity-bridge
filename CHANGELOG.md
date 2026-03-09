# Changelog

## [1.3.1] - 2026-03-09

### Bug Fixes
- Add Linux support to `scripts/start_antigravity.sh` by launching the local `antigravity` binary instead of relying on macOS `open`
- Improve startup diagnostics by waiting for CDP readiness and surfacing the Antigravity launcher log on failure
- Handle bridge port collisions gracefully by reporting existing `/health` status instead of crashing with `OSError: [Errno 98]`

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
