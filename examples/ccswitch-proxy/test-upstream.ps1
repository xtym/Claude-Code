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
