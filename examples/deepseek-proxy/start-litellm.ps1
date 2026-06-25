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

function Write-Utf8NoBomFile {
  param(
    [string]$Path,
    [string]$Content
  )
  $utf8NoBom = New-Object System.Text.UTF8Encoding $false
  [System.IO.File]::WriteAllText($Path, $Content, $utf8NoBom)
}

function New-LiteLlmModelEntry {
  param(
    [string]$ModelName,
    [string]$UpstreamModelId,
    [string]$UserAgent
  )
  @"
  - model_name: $ModelName
    litellm_params:
      model: openai/$UpstreamModelId
      api_key: os.environ/OPENAI_API_KEY
      api_base: os.environ/OPENAI_API_BASE
      timeout: 600
      stream_timeout: 120
      extra_headers:
        User-Agent: "$UserAgent"
"@
}

$models = @()
$seen = @{}

function Add-ModelRoute {
  param([string]$Name, [string]$UpstreamId)
  if ($seen.ContainsKey($Name)) { return }
  $seen[$Name] = $true
  $script:models += New-LiteLlmModelEntry -ModelName $Name -UpstreamModelId $UpstreamId -UserAgent $env:UPSTREAM_USER_AGENT
}

Add-ModelRoute -Name $env:LLM_MODEL -UpstreamId $env:OPENAI_MODEL_ID
if ($env:LLM_MODEL_OPUS -ne $env:LLM_MODEL) {
  Add-ModelRoute -Name $env:LLM_MODEL_OPUS -UpstreamId $env:OPENAI_MODEL_ID_OPUS
}

$generated = @"
# Auto-generated from .env - do not edit manually
model_list:
$($models -join "`n")

"@ + (Get-Content (Join-Path $here "litellm_config.yaml") -Raw -Encoding UTF8)

$generatedPath = Join-Path $here "litellm_config.generated.yaml"
Write-Utf8NoBomFile -Path $generatedPath -Content $generated

Write-Host "Upstream: $env:OPENAI_API_BASE" -ForegroundColor DarkGray
Write-Host "Models:   $($seen.Keys -join ', ') -> openai/$($env:OPENAI_MODEL_ID)" -ForegroundColor DarkGray
Write-Host "Proxy:    http://$($env:PROXY_HOST):$($env:PROXY_PORT) (Anthropic /v1/messages + OpenAI /v1/chat/completions)" -ForegroundColor Cyan
Write-Host ""
Write-Host "Preflight upstream (test-upstream.ps1)..." -ForegroundColor DarkGray
& (Join-Path $here "test-upstream.ps1")
if ($LASTEXITCODE -ne 0) {
  Write-Host ""
  Write-Host "Upstream check failed — LiteLLM will start but Agent / ArcReel text calls may 502 or hang." -ForegroundColor Yellow
  Write-Host "Gateway may be temporarily overloaded; relay will auto-retry with UA rotation." -ForegroundColor Yellow
  $answer = Read-Host "Continue anyway? [y/N]"
  if ($answer -notmatch '^[yY]') { exit 1 }
}

Write-Host "Starting LiteLLM with upstream retry relay (run_litellm.py)..." -ForegroundColor DarkGray
python (Join-Path $here "run_litellm.py")
