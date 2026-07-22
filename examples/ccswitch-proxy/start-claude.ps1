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
