# CC Switch Proxy Launcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `examples/ccswitch-proxy/` so this repo’s Claude Code CLI starts against a running CC Switch proxy at `http://127.0.0.1:15721` without LiteLLM.

**Architecture:** PowerShell launcher mirrors `examples/deepseek-proxy/` but points `ANTHROPIC_BASE_URL` at CC Switch. `.env` supplies optional API key (placeholder if missing) and required `LLM_MODEL`. `test-upstream.ps1` TCP/HTTP-probes the proxy; `start-claude.ps1` warns on failure and continues.

**Tech Stack:** PowerShell 5+, Bun (`bun run dev`), local CC Switch desktop proxy (not started by this example).

**Spec reference:** `docs/superpowers/specs/2026-07-22-ccswitch-proxy-design.md`

---

## File Map

| File | Responsibility |
|------|----------------|
| `examples/ccswitch-proxy/.env.example` | Committed template for local `.env` |
| `examples/ccswitch-proxy/load-env.ps1` | Parse `.env`, defaults, key resolution, require `LLM_MODEL` |
| `examples/ccswitch-proxy/test-upstream.ps1` | Probe `CCSWITCH_BASE_URL`; exit non-zero if down |
| `examples/ccswitch-proxy/start-claude.ps1` | Set `ANTHROPIC_*` + proxy flags → `bun run dev` |
| `examples/ccswitch-proxy/claude-settings.snippet.json` | Reference-only settings env snippet |

No TypeScript / LiteLLM / Python in this example.

---

### Task 1: `.env.example` + `load-env.ps1`

**Files:**
- Create: `examples/ccswitch-proxy/.env.example`
- Create: `examples/ccswitch-proxy/load-env.ps1`

- [ ] **Step 1: Create the directory and `.env.example`**

```powershell
New-Item -ItemType Directory -Force -Path "examples/ccswitch-proxy" | Out-Null
```

Write `examples/ccswitch-proxy/.env.example`:

```env
# Copy to .env and edit:
#   copy .env.example .env

# CC Switch local proxy (desktop app must be running with Proxy enabled)
CCSWITCH_BASE_URL=http://127.0.0.1:15721

# Optional. If empty, load-env.ps1 uses sk-ccswitch placeholder.
# Prefer ANTHROPIC_API_KEY; ANTHROPIC_AUTH_TOKEN is used only when API key is empty.
# ANTHROPIC_API_KEY=
# ANTHROPIC_AUTH_TOKEN=

# Model id Claude Code will request (must exist / be routed in CC Switch)
LLM_MODEL=claude-sonnet-4-5

# Optional opus-tier model (defaults to LLM_MODEL)
# LLM_MODEL_OPUS=claude-opus-4-5
```

- [ ] **Step 2: Create `load-env.ps1`**

Write `examples/ccswitch-proxy/load-env.ps1`:

```powershell
# Shared .env loader for start-claude.ps1 / test-upstream.ps1
param(
  [string]$EnvFile = (Join-Path $PSScriptRoot ".env")
)

function Import-DotEnvFile {
  param([string]$Path)

  if (-not (Test-Path $Path)) {
    throw "Missing $Path — copy .env.example to .env and fill in values."
  }

  Get-Content $Path | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
    $name, $value = $_ -split '=', 2
    $name = $name.Trim()
    if (-not $name) { return }
    Set-Item -Path "env:$name" -Value $value.Trim()
  }
}

function Set-EnvDefault {
  param(
    [string]$Name,
    [string]$Default
  )
  $current = [Environment]::GetEnvironmentVariable($Name, 'Process')
  if (-not $current) {
    [Environment]::SetEnvironmentVariable($Name, $Default, 'Process')
  }
}

Import-DotEnvFile -Path $EnvFile

Set-EnvDefault -Name "CCSWITCH_BASE_URL" -Default "http://127.0.0.1:15721"

if (-not $env:LLM_MODEL) {
  throw "LLM_MODEL is required in .env (model id Claude Code will request via CC Switch)"
}

Set-EnvDefault -Name "LLM_MODEL_OPUS" -Default $env:LLM_MODEL

# Key resolution: API_KEY → AUTH_TOKEN → placeholder
if (-not $env:ANTHROPIC_API_KEY) {
  if ($env:ANTHROPIC_AUTH_TOKEN) {
    $env:ANTHROPIC_API_KEY = $env:ANTHROPIC_AUTH_TOKEN
  } else {
    $env:ANTHROPIC_API_KEY = "sk-ccswitch"
  }
}

$env:CCSWITCH_BASE_URL = $env:CCSWITCH_BASE_URL.TrimEnd('/')
```

- [ ] **Step 3: Smoke-test load-env (missing `.env` fails)**

Run from repo root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "examples/ccswitch-proxy/load-env.ps1"
```

Expected: throws `Missing ...\.env — copy .env.example to .env...`

- [ ] **Step 4: Create local `.env` from example and re-test**

```powershell
Copy-Item examples/ccswitch-proxy/.env.example examples/ccswitch-proxy/.env
powershell -NoProfile -Command ". ./examples/ccswitch-proxy/load-env.ps1; Write-Host `$env:CCSWITCH_BASE_URL; Write-Host `$env:ANTHROPIC_API_KEY; Write-Host `$env:LLM_MODEL"
```

Expected stdout includes:

```
http://127.0.0.1:15721
sk-ccswitch
claude-sonnet-4-5
```

- [ ] **Step 5: Commit**

```powershell
git add examples/ccswitch-proxy/.env.example examples/ccswitch-proxy/load-env.ps1
git commit -m "Add ccswitch-proxy env template and loader"
```

Do **not** commit `examples/ccswitch-proxy/.env`.

---

### Task 2: `test-upstream.ps1`

**Files:**
- Create: `examples/ccswitch-proxy/test-upstream.ps1`

- [ ] **Step 1: Write `test-upstream.ps1`**

Write `examples/ccswitch-proxy/test-upstream.ps1`:

```powershell
# Probe CC Switch local proxy (does not require a successful LLM completion).
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here
. (Join-Path $here "load-env.ps1")

$base = $env:CCSWITCH_BASE_URL
Write-Host "Testing CC Switch proxy: $base" -ForegroundColor Cyan

$uri = [Uri]$base
$hostName = $uri.Host
$port = if ($uri.Port -gt 0) { $uri.Port } else { 80 }

try {
  $client = New-Object System.Net.Sockets.TcpClient
  $iar = $client.BeginConnect($hostName, $port, $null, $null)
  $ok = $iar.AsyncWaitHandle.WaitOne(3000, $false)
  if (-not $ok -or -not $client.Connected) {
    throw "TCP connect timed out"
  }
  $client.EndConnect($iar)
  $client.Close()
  Write-Host "OK TCP $hostName`:$port is listening" -ForegroundColor Green
} catch {
  Write-Host "FAIL: cannot reach $base" -ForegroundColor Red
  Write-Host "Start CC Switch desktop app and enable Proxy (default http://127.0.0.1:15721)." -ForegroundColor Yellow
  Write-Host "Detail: $($_.Exception.Message)" -ForegroundColor DarkGray
  exit 1
}

# Optional HTTP probe — any HTTP response (even 4xx) means the proxy is up
try {
  $resp = Invoke-WebRequest -Uri $base -Method GET -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
  Write-Host "OK HTTP $($resp.StatusCode)" -ForegroundColor Green
} catch {
  $status = $null
  if ($_.Exception.Response) {
    $status = [int]$_.Exception.Response.StatusCode
  }
  if ($status) {
    Write-Host "OK HTTP $status (proxy responding)" -ForegroundColor Green
  } else {
    Write-Host "WARN TCP OK but HTTP probe failed: $($_.Exception.Message)" -ForegroundColor Yellow
    Write-Host "Proxy may still work for /v1/messages — try start-claude.ps1" -ForegroundColor DarkGray
  }
}

exit 0
```

- [ ] **Step 2: Run probe with CC Switch stopped (or port closed)**

```powershell
cd examples/ccswitch-proxy
powershell -NoProfile -ExecutionPolicy Bypass -File .\test-upstream.ps1
echo "exit=$LASTEXITCODE"
```

Expected when port closed: `FAIL: cannot reach...`, `exit=1`, message mentioning enable Proxy.

- [ ] **Step 3: Run probe with CC Switch Proxy enabled**

Same command. Expected: `OK TCP 127.0.0.1:15721 is listening`, exit `0`.

- [ ] **Step 4: Commit**

```powershell
git add examples/ccswitch-proxy/test-upstream.ps1
git commit -m "Add ccswitch-proxy upstream probe script"
```

---

### Task 3: `start-claude.ps1`

**Files:**
- Create: `examples/ccswitch-proxy/start-claude.ps1`

- [ ] **Step 1: Write `start-claude.ps1`**

Write `examples/ccswitch-proxy/start-claude.ps1`:

```powershell
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $here "..\..")

. (Join-Path $here "load-env.ps1")

# Non-blocking probe
& (Join-Path $here "test-upstream.ps1")
if ($LASTEXITCODE -ne 0) {
  Write-Host ""
  Write-Host "CC Switch probe failed — Claude Code will still start, but API calls may fail." -ForegroundColor Yellow
  Write-Host "Enable Proxy in CC Switch, then retry." -ForegroundColor Yellow
}

$proxyBase = $env:CCSWITCH_BASE_URL

$env:ANTHROPIC_BASE_URL = $proxyBase
# ANTHROPIC_API_KEY already resolved in load-env.ps1

$env:ANTHROPIC_MODEL = $env:LLM_MODEL
$env:ANTHROPIC_DEFAULT_SONNET_MODEL = $env:LLM_MODEL
$env:ANTHROPIC_DEFAULT_HAIKU_MODEL = $env:LLM_MODEL
$env:ANTHROPIC_DEFAULT_OPUS_MODEL = $env:LLM_MODEL_OPUS
$env:ANTHROPIC_SMALL_FAST_MODEL = $env:LLM_MODEL

$env:CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS = "1"
$env:ENABLE_TOOL_SEARCH = "false"
$env:API_TIMEOUT_MS = "600000"
$env:CLAUDE_CODE_CUSTOM_PROXY = "1"
$env:DISABLE_TELEMETRY = "1"
$env:CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = "1"

function Resolve-BunExecutable {
  $bunDir = Join-Path $env:USERPROFILE ".bun\bin"
  if (Test-Path $bunDir) {
    $env:Path = "$bunDir;$env:Path"
  }

  $cmd = Get-Command bun -ErrorAction SilentlyContinue
  if ($cmd -and $cmd.Source) {
    return $cmd.Source
  }

  $candidates = @(
    (Join-Path $env:USERPROFILE ".bun\bin\bun.exe")
    (Join-Path $env:LOCALAPPDATA "bun\bin\bun.exe")
  )
  foreach ($path in $candidates) {
    if (Test-Path $path) {
      return $path
    }
  }

  throw @"
Bun not found. Install it, then reopen the terminal:

  powershell -NoProfile -ExecutionPolicy Bypass -Command "irm bun.sh/install.ps1 | iex"

Or: https://bun.sh
"@
}

$bun = Resolve-BunExecutable

Write-Host "Claude -> $proxyBase | model=$($env:LLM_MODEL) (opus=$($env:LLM_MODEL_OPUS))" -ForegroundColor Cyan
Write-Host "Custom proxy mode: OAuth / Claude login skipped" -ForegroundColor DarkGray

Set-Location $repoRoot
& $bun run dev @args
```

- [ ] **Step 2: Dry-run env injection without staying in REPL (optional sanity)**

If you only want to verify env wiring without interactive session, run a short PowerShell check that sources the same assignments:

```powershell
cd examples/ccswitch-proxy
. .\load-env.ps1
$env:ANTHROPIC_BASE_URL = $env:CCSWITCH_BASE_URL
Write-Host "BASE=$($env:ANTHROPIC_BASE_URL) KEY=$($env:ANTHROPIC_API_KEY) MODEL=$($env:LLM_MODEL)"
```

Expected: `BASE=http://127.0.0.1:15721 KEY=sk-ccswitch MODEL=claude-sonnet-4-5` (or your `.env` overrides).

- [ ] **Step 3: Manual boot (with CC Switch running)**

```powershell
cd examples/ccswitch-proxy
.\start-claude.ps1
```

Expected:
- Probe prints OK (or yellow warn if down)
- Cyan line: `Claude -> http://127.0.0.1:15721 | model=...`
- CLI interactive prompt appears
- One user message completes via ccswitch (provider must be configured in CC Switch)

- [ ] **Step 4: Commit**

```powershell
git add examples/ccswitch-proxy/start-claude.ps1
git commit -m "Add ccswitch-proxy start-claude launcher"
```

---

### Task 4: Settings snippet + final check

**Files:**
- Create: `examples/ccswitch-proxy/claude-settings.snippet.json`

- [ ] **Step 1: Write snippet**

Write `examples/ccswitch-proxy/claude-settings.snippet.json`:

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:15721",
    "ANTHROPIC_API_KEY": "sk-ccswitch",
    "ANTHROPIC_MODEL": "claude-sonnet-4-5",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "claude-sonnet-4-5",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "claude-sonnet-4-5",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "claude-sonnet-4-5",
    "ANTHROPIC_SMALL_FAST_MODEL": "claude-sonnet-4-5",
    "CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS": "1",
    "ENABLE_TOOL_SEARCH": "false",
    "API_TIMEOUT_MS": "600000",
    "CLAUDE_CODE_CUSTOM_PROXY": "1",
    "DISABLE_TELEMETRY": "1",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"
  },
  "_comment": "Reference only. Prefer .\\start-claude.ps1. ANTHROPIC_* model values must match LLM_MODEL / LLM_MODEL_OPUS in .env. CC Switch desktop Proxy must be running on CCSWITCH_BASE_URL."
}
```

- [ ] **Step 2: Confirm tree**

```powershell
Get-ChildItem examples/ccswitch-proxy | Select-Object Name
```

Expected names include: `.env.example`, `load-env.ps1`, `test-upstream.ps1`, `start-claude.ps1`, `claude-settings.snippet.json` (and local `.env` untracked).

- [ ] **Step 3: Confirm `.env` is not staged**

```powershell
git status --short examples/ccswitch-proxy
```

Expected: tracked scripts + `.env.example` + snippet; `.env` either untracked (`??`) or absent from commit. Do not `git add` `.env`.

- [ ] **Step 4: Commit snippet**

```powershell
git add examples/ccswitch-proxy/claude-settings.snippet.json
git commit -m "Add ccswitch-proxy settings snippet reference"
```

- [ ] **Step 5: Update design spec status (optional one-liner)**

In `docs/superpowers/specs/2026-07-22-ccswitch-proxy-design.md`, change:

```markdown
**Status:** Approved (design) — awaiting implementation plan
```

to:

```markdown
**Status:** Implemented — see `docs/superpowers/plans/2026-07-22-ccswitch-proxy.md`
```

```powershell
git add docs/superpowers/specs/2026-07-22-ccswitch-proxy-design.md
git commit -m "Mark ccswitch-proxy design as implemented"
```

(Only do Step 5 after Tasks 1–4 are done and validated.)

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| `examples/ccswitch-proxy/` layout | 1–4 |
| `CCSWITCH_BASE_URL` default `:15721` | Task 1 |
| Optional key / placeholder `sk-ccswitch` | Task 1 |
| `ANTHROPIC_AUTH_TOKEN` fallback | Task 1 |
| Required `LLM_MODEL` + optional opus | Task 1 |
| `test-upstream.ps1` non-zero on fail | Task 2 |
| `start-claude.ps1` warn + continue | Task 3 |
| `ANTHROPIC_*` + custom proxy flags | Task 3 |
| `bun run dev` from repo root | Task 3 |
| Settings snippet reference only | Task 4 |
| No LiteLLM / no settings mutation | All (out of scope) |
| Do not commit secrets `.env` | Task 1 Step 5, Task 4 Step 3 |

---

## Self-review notes

- No TBD/placeholder steps; full script bodies included.
- Key resolution and model mapping match the approved spec.
- Probe does not require LLM success (TCP + optional HTTP).
- Commits are frequent and exclude `.env`.
