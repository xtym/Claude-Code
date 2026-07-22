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

# Key resolution: API_KEY → AUTH_TOKEN → placeholder.
# freebuff2api upstream wants Bearer; set both so Claude Code (x-api-key) and
# CC Switch provider remapping (AUTH_TOKEN) stay aligned.
if (-not $env:ANTHROPIC_API_KEY) {
  if ($env:ANTHROPIC_AUTH_TOKEN) {
    $env:ANTHROPIC_API_KEY = $env:ANTHROPIC_AUTH_TOKEN
  } else {
    $env:ANTHROPIC_API_KEY = "sk-ccswitch"
  }
}
if (-not $env:ANTHROPIC_AUTH_TOKEN -and $env:ANTHROPIC_API_KEY) {
  $env:ANTHROPIC_AUTH_TOKEN = $env:ANTHROPIC_API_KEY
}

$env:CCSWITCH_BASE_URL = $env:CCSWITCH_BASE_URL.TrimEnd('/')
