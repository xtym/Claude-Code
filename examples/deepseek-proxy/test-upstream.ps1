# Quick upstream health check before starting LiteLLM or debugging 502s.
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here
. (Join-Path $here "load-env.ps1")

$body = @{
  model      = $env:OPENAI_MODEL_ID
  messages   = @(@{ role = "user"; content = "reply with ok" })
  max_tokens = 16
} | ConvertTo-Json -Depth 5 -Compress

$uri = "$($env:OPENAI_API_BASE)/chat/completions"
$userAgents = @(
  $env:UPSTREAM_USER_AGENT
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
) | Select-Object -Unique

Write-Host "Testing upstream: $uri" -ForegroundColor Cyan
Write-Host "Model: $($env:OPENAI_MODEL_ID)" -ForegroundColor DarkGray

foreach ($attempt in 1..4) {
  foreach ($ua in $userAgents) {
    $headers = @{
      Authorization  = "Bearer $($env:OPENAI_API_KEY)"
      "Content-Type" = "application/json"
      "User-Agent"   = $ua
    }
    Write-Host "  attempt $attempt UA: $($ua.Substring(0, [Math]::Min(50, $ua.Length)))..." -ForegroundColor DarkGray
    try {
      $resp = Invoke-WebRequest -Uri $uri -Method POST -Headers $headers -Body $body -TimeoutSec 120 -UseBasicParsing
      Write-Host "OK $($resp.StatusCode)" -ForegroundColor Green
      if ($resp.Content.Length -gt 400) {
        Write-Host ($resp.Content.Substring(0, 400) + "...")
      } else {
        Write-Host $resp.Content
      }
      exit 0
    } catch {
      $status = $null
      $snippet = $_.Exception.Message
      if ($_.Exception.Response) {
        $status = [int]$_.Exception.Response.StatusCode
        try {
          $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
          $snippet = $reader.ReadToEnd()
          $reader.Close()
        } catch {}
      }
      if ($snippet.Length -gt 120) { $snippet = $snippet.Substring(0, 120) + "..." }
      Write-Host "    failed status=$status $snippet" -ForegroundColor Yellow
    }
    Start-Sleep -Milliseconds 400
  }
}

Write-Host "FAILED: all retries exhausted" -ForegroundColor Red
Write-Host ""
Write-Host "FreeBuff gateway tips (keep same OPENAI_API_BASE):" -ForegroundColor Yellow
Write-Host "  - Do NOT use curl/8.0 or OpenAI/Python UA (often 502/403)" -ForegroundColor Yellow
Write-Host "  - Set UPSTREAM_USER_AGENT in .env to a browser UA (see .env.example)" -ForegroundColor Yellow
Write-Host "  - Retry later if gateway is overloaded (intermittent 502)" -ForegroundColor Yellow
exit 1
