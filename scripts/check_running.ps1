<#
  띄운 "뒤에" 제대로 떴는지 확인합니다.

    powershell -ExecutionPolicy Bypass -File scripts\check_running.ps1
    powershell -ExecutionPolicy Bypass -File scripts\check_running.ps1 -HostUrl http://사내서버주소
#>
param(
  [string]$HostUrl = 'http://localhost'
)

$ErrorActionPreference = 'Continue'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

Set-Location (Split-Path $PSScriptRoot -Parent)

$HostUrl = $HostUrl.TrimEnd('/')
$Api = "$HostUrl`:8000"
$Web = "$HostUrl`:3000"

$script:Pass = 0; $script:Fail = 0
function Ok($m)   { Write-Host "  [ OK ] $m" -ForegroundColor Green; $script:Pass++ }
function Bad($m)  { Write-Host "  [안됨] $m" -ForegroundColor Red;   $script:Fail++ }
function Note($m) { Write-Host "         $m" -ForegroundColor DarkGray }
function Section($m) { Write-Host ""; Write-Host "== $m ==" -ForegroundColor Cyan }

# .env 가 없으면 도커 없이 띄운 기록에서 찾습니다(scripts\run_local.ps1 이 남깁니다).
$EnvFile = '.env'
$LocalMode = $false
if (-not (Test-Path $EnvFile)) {
  if (Test-Path '.local-run\creds') { $EnvFile = '.local-run\creds'; $LocalMode = $true }
}

$envMap = @{}
if (Test-Path $EnvFile) {
  foreach ($line in (Get-Content $EnvFile -Encoding UTF8)) {
    if ($line -match '^\s*#') { continue }
    $i = $line.IndexOf('=')
    if ($i -gt 0) { $envMap[$line.Substring(0,$i).Trim()] = $line.Substring($i+1).Trim() }
  }
}
function Env2($k) { if ($envMap.ContainsKey($k)) { return $envMap[$k] } else { return '' } }

# ── 1. 컨테이너 ───────────────────────────────────────────────────
Section "1. 컨테이너가 다 떴나"
$psOut = $null
if (-not $LocalMode) { $psOut = docker compose ps --format '{{.Service}} {{.State}}' 2>$null }
if ($LocalMode) {
  Note "도커 없이 띄운 모드입니다(.local-run\). 컨테이너 점검은 건너뜁니다."
} elseif ($LASTEXITCODE -eq 0 -and $psOut) {
  $lines = @($psOut | Where-Object { $_ })
  $downs = @($lines | Where-Object { $_ -notmatch ' running$' })
  if ($downs.Count -eq 0) { Ok "서비스 $($lines.Count)개가 모두 running" }
  else {
    Bad "떠 있지 않은 서비스가 있습니다:"
    $downs | ForEach-Object { Write-Host "           $_" }
    Note "docker compose logs --tail=50 <서비스이름>  으로 이유를 보세요."
  }
} else {
  Bad "docker compose ps 가 실패했습니다 — 도커가 켜져 있고 저장소 폴더에서 실행했는지 보세요"
  Note "도커를 못 쓰는 PC 라면 scripts\run_local.ps1 로 띄우세요."
}

# ── 2. 백엔드 ─────────────────────────────────────────────────────
Section "2. 백엔드 ($Api)"
$health = $null
try { $health = (Invoke-WebRequest -Uri "$Api/health" -UseBasicParsing -TimeoutSec 15).Content } catch {}
if (-not $health) {
  Bad "$Api/health 에 닿지 않습니다"
  Note "docker compose logs --tail=50 backend   — 설정 점검에 걸려 안 떴을 수 있습니다."
} else {
  $errs = @(($health -split ',') | Where-Object { $_ -match 'error' })
  if ($health -match '"status"\s*:\s*"ok"') { Ok "백엔드 정상 (DB·Redis 연결됨)" }
  elseif ($LocalMode -and ($errs.Count -gt 0) -and -not ($errs | Where-Object { $_ -notmatch 'redis' })) {
    Ok "백엔드 정상 (DB 연결됨. Redis 는 도커 없이 띄울 때 안 씁니다)"
  }
  else {
    Bad "백엔드는 떴지만 일부가 안 됩니다:"
    ($health -split ',') | Where-Object { $_ -match 'error' } | ForEach-Object {
      Write-Host ("           " + ($_ -replace '["{}]',''))
    }
  }
  ($health -split ',') | Where-Object { $_ -match 'llm_' } | ForEach-Object {
    Write-Host ("           " + ($_ -replace '["{}]','')) -ForegroundColor DarkGray
  }
}

# ── 3. 화면 ───────────────────────────────────────────────────────
Section "3. 화면 ($Web)"
$code = 0
try { $code = (Invoke-WebRequest -Uri $Web -UseBasicParsing -TimeoutSec 20).StatusCode } catch {}
if ($code -eq 200) { Ok "화면이 열립니다 — 브라우저로 $Web 접속하세요" }
else { Bad "화면이 안 열립니다 (HTTP $code) — docker compose logs --tail=50 frontend" }

# ── 4. 로그인 ─────────────────────────────────────────────────────
Section "4. 로그인"
$aid = Env2 'ADMIN_ID'; $apw = Env2 'ADMIN_PASSWORD'
$token = ''
if ((-not $aid) -or (-not $apw)) {
  Bad "ADMIN_ID / ADMIN_PASSWORD 를 찾지 못해 로그인 확인을 못 합니다 (.env 또는 .local-run\creds)"
} else {
  $body = (@{ user_id = $aid; password = $apw } | ConvertTo-Json -Compress)
  try {
    $resp = Invoke-RestMethod -Uri "$Api/api/auth/login" -Method Post -TimeoutSec 15 `
              -ContentType 'application/json; charset=utf-8' `
              -Body ([Text.Encoding]::UTF8.GetBytes($body))
    $token = $resp.token
  } catch { $token = '' }
  if ($token) { Ok "관리자($aid) 로그인 성공" }
  else {
    Bad "로그인 실패 — 사번/비밀번호를 확인하세요"
    Note "계정은 '처음 기동할 때' 만들어집니다. .env 의 비밀번호만 나중에 바꾸면 반영되지 않습니다."
    Note "ADMIN_RESET_PASSWORD=true 로 두고 docker compose restart backend 하면 덮어씁니다."
  }
}

# ── 5. 앱스토어 ───────────────────────────────────────────────────
Section "5. 앱스토어에 앱이 올라왔나"
if ($token) {
  $apps = @()
  try { $apps = Invoke-RestMethod -Uri "$Api/api/apps" -Headers @{ Authorization = "Bearer $token" } -TimeoutSec 20 } catch {}
  if ($apps.Count -gt 0) {
    Ok "앱 $($apps.Count)개가 등록되어 있습니다"
    $down = @($apps | Where-Object { $_.status -eq 'unreachable' } | ForEach-Object { $_.name })
    if ($down.Count -eq 0) { Ok "응답 안 하는 앱 없음" }
    else { Bad ("응답이 없는 앱: " + ($down -join ', ')) }
  } else {
    Bad "등록된 앱이 없습니다"
    Note ".env 의 SEED_FILE 경로와 config/apps.seed*.json 을 보세요."
    Note "앱보다 백엔드가 먼저 떠서 기능 목록을 못 읽었을 수도 있습니다: docker compose restart backend"
  }
} else { Note "로그인이 안 돼 건너뜁니다." }

# ── 6. 공식 앱 포트 ───────────────────────────────────────────────
Section "6. 공식 앱 포트"
$badPorts = @()
foreach ($p in @(9101,9102,9103,9111,9112,9113,9114,9115,9116,9117,9118,9119)) {
  $alive = $false
  try {
    # MCP 는 그냥 GET 하면 400/405/406 을 돌려줍니다. 그래도 "살아 있다"는 뜻입니다.
    Invoke-WebRequest -Uri "$HostUrl`:$p/mcp" -UseBasicParsing -TimeoutSec 8 | Out-Null
    $alive = $true
  } catch {
    if ($_.Exception.Response) { $alive = $true }
  }
  if (-not $alive) { $badPorts += $p }
}
if ($badPorts.Count -eq 0) { Ok "공식 앱 12개 포트가 모두 응답합니다" }
else { Bad ("응답 없는 포트: " + ($badPorts -join ' ') + "  (docker compose logs --tail=30 <해당 앱>)") }

# ── 마무리 ────────────────────────────────────────────────────────
Write-Host ""
Write-Host "────────────────────────────────────────"
Write-Host ("  통과 {0} · 안됨 {1}" -f $script:Pass, $script:Fail)
if ($script:Fail -gt 0) {
  if ($LocalMode) { Write-Host "  기록 보기:  .local-run\logs\  (안 뜬 것의 이름 .log 를 여세요)" }
  else { Write-Host "  전체 로그 한 번에 보기:  docker compose logs --tail=80" }
  Write-Host ""
  exit 1
}
Write-Host "  다 떴습니다. 브라우저로 $Web 접속해서 로그인해 보세요."
Write-Host ""
