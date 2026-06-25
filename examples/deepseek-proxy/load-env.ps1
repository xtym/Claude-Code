# Shared .env loader for start-litellm.ps1 / start-claude.ps1
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

# --- Upstream OpenAI-compatible API ---
if (-not $env:OPENAI_API_BASE) { throw "OPENAI_API_BASE is required in .env (e.g. https://api.deepseek.com/v1)" }
if (-not $env:OPENAI_API_KEY) { throw "OPENAI_API_KEY is required in .env" }
if (-not $env:LLM_MODEL) { throw "LLM_MODEL is required in .env (model id Claude Code will request)" }

Set-EnvDefault -Name "OPENAI_MODEL_ID" -Default $env:LLM_MODEL
Set-EnvDefault -Name "LLM_MODEL_OPUS" -Default $env:LLM_MODEL
Set-EnvDefault -Name "OPENAI_MODEL_ID_OPUS" -Default $env:LLM_MODEL_OPUS

# --- Local LiteLLM proxy (Claude Code -> proxy) ---
Set-EnvDefault -Name "PROXY_HOST" -Default "127.0.0.1"
Set-EnvDefault -Name "PROXY_PORT" -Default "4000"
Set-EnvDefault -Name "PROXY_API_KEY" -Default "proxy-local"

Set-EnvDefault -Name "UPSTREAM_USER_AGENT" -Default "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Normalize base URL (no trailing slash)
$env:OPENAI_API_BASE = $env:OPENAI_API_BASE.TrimEnd('/')
