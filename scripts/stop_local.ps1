<#
  scripts\run_local.ps1 로 띄운 것들을 내립니다.

    powershell -ExecutionPolicy Bypass -File scripts\stop_local.ps1
#>
$ErrorActionPreference = 'Continue'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

Set-Location (Split-Path $PSScriptRoot -Parent)
$RunDir  = Join-Path (Get-Location).Path '.local-run'
$PidFile = Join-Path $RunDir 'pids'

$n = 0
if (Test-Path $PidFile) {
  foreach ($line in (Get-Content $PidFile)) {
    if (-not $line.Trim()) { continue }
    try { Stop-Process -Id ([int]$line) -Force -ErrorAction Stop; $n++ } catch {}
  }
  Set-Content -Path $PidFile -Value '' -Encoding ascii
}

# 화면(next dev)과 npm 은 자식 프로세스를 더 만듭니다. 포트를 잡고 있으면 같이 내립니다.
Start-Sleep -Seconds 1
foreach ($p in @(3000,8000,9101,9102,9103,9111,9112,9113,9114,9115,9116,9117,9118,9119)) {
  try {
    foreach ($c in (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue)) {
      try { Stop-Process -Id $c.OwningProcess -Force -ErrorAction Stop; $n++ } catch {}
    }
  } catch {}
}

Write-Host "$n 개를 내렸습니다. 데이터는 .local-run\ 에 그대로 있습니다."
Write-Host "완전히 지우려면:  Remove-Item -Recurse -Force .local-run"
