$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $here "..\..")

. (Join-Path $here "load-env.ps1")

$proxyBase = "http://$($env:PROXY_HOST):$($env:PROXY_PORT)"

$env:ANTHROPIC_BASE_URL = $proxyBase
$env:ANTHROPIC_API_KEY = $env:PROXY_API_KEY

$env:ANTHROPIC_MODEL = $env:LLM_MODEL
$env:ANTHROPIC_DEFAULT_SONNET_MODEL = $env:LLM_MODEL
$env:ANTHROPIC_DEFAULT_HAIKU_MODEL = $env:LLM_MODEL
$env:ANTHROPIC_DEFAULT_OPUS_MODEL = $env:LLM_MODEL_OPUS
$env:ANTHROPIC_SMALL_FAST_MODEL = $env:LLM_MODEL

$env:CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS = "1"
$env:ENABLE_TOOL_SEARCH = "false"
$env:API_TIMEOUT_MS = "600000"

$bun = "bun"
if (-not (Get-Command bun -ErrorAction SilentlyContinue)) {
  $bun = Join-Path $env:USERPROFILE ".bun\bin\bun.exe"
}
if (-not (Test-Path $bun)) {
  throw "Bun not found. Install from https://bun.sh"
}

Write-Host "Claude -> $proxyBase | model=$($env:LLM_MODEL) | upstream=$($env:OPENAI_API_BASE)" -ForegroundColor Cyan

Set-Location $repoRoot
& $bun run dev @args
