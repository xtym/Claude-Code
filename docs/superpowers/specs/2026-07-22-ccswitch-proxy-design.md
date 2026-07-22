# CC Switch Proxy Launcher Design

**Date:** 2026-07-22  
**Status:** Implemented — see `docs/superpowers/plans/2026-07-22-ccswitch-proxy.md`  
**Approach:** Minimal launcher (Option 1) — no LiteLLM

## Summary

Add `examples/ccswitch-proxy/` so this Claude-Code repo can start against a already-running [CC Switch](https://github.com/farion1231/cc-switch) local proxy at `http://127.0.0.1:15721`. The example only sets `ANTHROPIC_*` env vars and runs `bun run dev`; it does **not** start LiteLLM or manage the CC Switch desktop app.

**Success criteria:**

1. With CC Switch proxy running on `:15721`, `.\start-claude.ps1` boots the restored CLI and API traffic goes to ccswitch.
2. API key is optional: `.env` value if present, otherwise placeholder `sk-ccswitch`.
3. Model IDs come from `.env` (`LLM_MODEL` / optional `LLM_MODEL_OPUS`) and map to `ANTHROPIC_*_MODEL`.
4. Missing ccswitch is diagnosable via `test-upstream.ps1` without blocking start (warn only).

---

## Architecture

```
Claude Code (bun run dev)
    │  ANTHROPIC_BASE_URL = CCSWITCH_BASE_URL
    │  ANTHROPIC_API_KEY  (or AUTH_TOKEN / placeholder)
    │  ANTHROPIC_*_MODEL  (from LLM_MODEL*)
    ▼
CC Switch Proxy (:15721)   ← must be started by user in desktop app
    ▼
Provider(s) configured inside CC Switch
```

CC Switch already speaks Anthropic Messages (and can convert OpenAI-format providers). Therefore this example does **not** insert LiteLLM between Claude Code and ccswitch (unlike `examples/deepseek-proxy/`).

---

## File layout

```
examples/ccswitch-proxy/
├── .env.example                 # committed template
├── .env                         # local only (copy from example; do not commit secrets)
├── load-env.ps1                 # parse .env + defaults
├── start-claude.ps1             # inject ANTHROPIC_* → bun run dev
├── test-upstream.ps1            # probe CCSWITCH_BASE_URL
└── claude-settings.snippet.json # optional settings.env reference
```

Mirror style of `examples/deepseek-proxy/` (PowerShell + `.env`), minus Python/LiteLLM.

---

## Environment variables

| Variable | Required | Default | Role |
|----------|----------|---------|------|
| `CCSWITCH_BASE_URL` | no | `http://127.0.0.1:15721` | Target proxy; trailing `/` stripped |
| `ANTHROPIC_API_KEY` | no | `sk-ccswitch` if unset and no auth token | Sent as Claude API key |
| `ANTHROPIC_AUTH_TOKEN` | no | — | If set and API key empty, use as key source |
| `LLM_MODEL` | **yes** | — | Maps to `ANTHROPIC_MODEL`, sonnet, haiku, small-fast |
| `LLM_MODEL_OPUS` | no | same as `LLM_MODEL` | Maps to `ANTHROPIC_DEFAULT_OPUS_MODEL` |

**Always set by `start-claude.ps1` (process env):**

- `ANTHROPIC_BASE_URL` = `CCSWITCH_BASE_URL`
- `CLAUDE_CODE_CUSTOM_PROXY=1` (skip OAuth / Claude login)
- `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1`
- `ENABLE_TOOL_SEARCH=false`
- `API_TIMEOUT_MS=600000`
- `DISABLE_TELEMETRY=1`
- `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`

---

## Script behavior

### `load-env.ps1`

1. Fail if `.env` missing; hint: copy `.env.example` → `.env`.
2. Load `KEY=VALUE` lines (skip blanks/comments).
3. Apply defaults for `CCSWITCH_BASE_URL`, key placeholder, `LLM_MODEL_OPUS`.
4. Require `LLM_MODEL`.
5. Normalize `CCSWITCH_BASE_URL` (no trailing slash).

Key resolution order:

1. `ANTHROPIC_API_KEY` if non-empty  
2. else `ANTHROPIC_AUTH_TOKEN` if non-empty (copy into `ANTHROPIC_API_KEY` for Claude Code)  
3. else `ANTHROPIC_API_KEY=sk-ccswitch`

### `test-upstream.ps1`

- Probe `CCSWITCH_BASE_URL` (TCP connect and/or lightweight HTTP request).
- On failure: print clear message that CC Switch Proxy must be enabled on `:15721`.
- Exit non-zero on failure so callers can detect status.
- Does not require a successful LLM completion (ccswitch may need a real provider for `/v1/messages`).

### `start-claude.ps1`

1. Dot-source `load-env.ps1`.
2. Optionally run `test-upstream.ps1`; on failure print warning and continue (or prompt continue — prefer warn + continue for DX).
3. Assign all `ANTHROPIC_*` and proxy flags above.
4. Resolve `bun` (same helper pattern as deepseek-proxy).
5. `Set-Location` repo root; `& bun run dev @args`.

### `claude-settings.snippet.json`

Reference-only JSON showing the same env keys for users who prefer settings merge over the launcher. Not applied automatically.

---

## Out of scope

- Starting or configuring the CC Switch desktop application
- LiteLLM / OpenAI→Anthropic conversion in this example
- Writing or mutating `~/.claude/settings.json`
- Cognitive-layer flags (remain in repo root `.env` if used)

---

## Testing / validation

1. Start CC Switch → enable Proxy on `127.0.0.1:15721`.
2. `copy .env.example .env` and set `LLM_MODEL` to a model id ccswitch routes.
3. `.\test-upstream.ps1` → OK when proxy listens.
4. `.\start-claude.ps1` → CLI boots; one chat turn succeeds through ccswitch.
5. Stop ccswitch → probe fails with actionable error; start still warns but boots.

---

## Implementation notes

- Reuse PowerShell patterns from `examples/deepseek-proxy/` (`load-env`, bun resolution, `@args`).
- Keep the example self-contained under `examples/ccswitch-proxy/`.
- Prefer not committing a real `.env` with secrets; ship `.env.example` only (local `.env` is developer-owned).
