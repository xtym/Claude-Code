$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  throw "Python is required. Install Python 3.10+ and retry."
}

. (Join-Path $here "load-env.ps1")

python -m pip install -q "litellm[proxy]"

$scriptsDir = python -c "import sysconfig; print(sysconfig.get_path('scripts'))"
$litellm = Join-Path $scriptsDir "litellm.exe"
if (-not (Test-Path $litellm)) {
  throw "litellm.exe not found after install. Try: python -m pip install 'litellm[proxy]'"
}

function New-LiteLlmModelEntry {
  param(
    [string]$ModelName,
    [string]$UpstreamModelId
  )
  @"
  - model_name: $ModelName
    litellm_params:
      model: openai/$UpstreamModelId
      api_key: os.environ/OPENAI_API_KEY
      api_base: os.environ/OPENAI_API_BASE
"@
}

$models = @()
$seen = @{}

function Add-ModelRoute {
  param([string]$Name, [string]$UpstreamId)
  if ($seen.ContainsKey($Name)) { return }
  $seen[$Name] = $true
  $script:models += New-LiteLlmModelEntry -ModelName $Name -UpstreamModelId $UpstreamId
}

Add-ModelRoute -Name $env:LLM_MODEL -UpstreamId $env:OPENAI_MODEL_ID
if ($env:LLM_MODEL_OPUS -ne $env:LLM_MODEL) {
  Add-ModelRoute -Name $env:LLM_MODEL_OPUS -UpstreamId $env:OPENAI_MODEL_ID_OPUS
}

$generated = @"
# Auto-generated from .env — do not edit manually
model_list:
$($models -join "`n")

"@ + (Get-Content (Join-Path $here "litellm_config.yaml") -Raw)

$generatedPath = Join-Path $here "litellm_config.generated.yaml"
Set-Content -Path $generatedPath -Value $generated -Encoding utf8

Write-Host "Upstream: $env:OPENAI_API_BASE" -ForegroundColor DarkGray
Write-Host "Models:   $($seen.Keys -join ', ') -> openai/($env:OPENAI_MODEL_ID)" -ForegroundColor DarkGray
Write-Host "Proxy:    http://$($env:PROXY_HOST):$($env:PROXY_PORT) (Anthropic /v1/messages)" -ForegroundColor Cyan

& $litellm --config $generatedPath --host $env:PROXY_HOST --port $env:PROXY_PORT
