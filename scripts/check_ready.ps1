<#
  회사 PC(Windows)에서 Workflow Auto 를 띄우기 "전에" 필요한 것이 다 있는지 점검합니다.

    powershell -ExecutionPolicy Bypass -File scripts\check_ready.ps1
    powershell -ExecutionPolicy Bypass -File scripts\check_ready.ps1 -Install   # 없는 프로그램 자동 설치 시도
    powershell -ExecutionPolicy Bypass -File scripts\check_ready.ps1 -Fix       # .env 를 회사 프로필에서 만들기
    powershell -ExecutionPolicy Bypass -File scripts\check_ready.ps1 -Fix -Simple # "그냥 떠는지만 보는" 확인용 .env
    powershell -ExecutionPolicy Bypass -File scripts\check_ready.ps1 -Deep      # 사내 미러에서 실제로 받아 보기(느림)
#>
param(
  [switch]$Install,
  [switch]$Fix,
  [switch]$Simple,
  [switch]$Deep
)

$ErrorActionPreference = 'Continue'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

Set-Location (Split-Path $PSScriptRoot -Parent)

$script:Pass = 0; $script:Warn = 0; $script:Fail = 0; $script:DevMode = $false

function Ok($m)   { Write-Host "  [ OK ] $m" -ForegroundColor Green;  $script:Pass++ }
function Warn($m) { Write-Host "  [주의] $m" -ForegroundColor Yellow; $script:Warn++ }
function Bad($m)  { Write-Host "  [막힘] $m" -ForegroundColor Red;    $script:Fail++ }
# 확인용(APP_ENV=dev)일 때는 운영 전용 점검을 '주의' 로만 알립니다.
function BadProd($m) { if ($script:DevMode) { Warn $m } else { Bad $m } }
function Note($m) { Write-Host "         $m" -ForegroundColor DarkGray }
function Section($m) { Write-Host ""; Write-Host "== $m ==" -ForegroundColor Cyan }

function Have($name) { return [bool](Get-Command $name -ErrorAction SilentlyContinue) }

function TryWinget($id, $label) {
  if (-not $Install) { Note "자동 설치하려면 -Install 옵션을 붙이세요 (winget 필요, 관리자 권한을 물어봅니다)"; return }
  if (-not (Have 'winget')) { Note "winget 이 없어 자동 설치를 못 합니다. 사내 소프트웨어 센터에서 $label 를 설치하세요."; return }
  Note "winget 으로 $label 설치를 시도합니다..."
  winget install --id $id --accept-source-agreements --accept-package-agreements -e 2>&1 | Out-Null
  if ($LASTEXITCODE -eq 0) { Note "$label 설치가 끝났습니다. PowerShell 창을 새로 열고 다시 실행하세요." }
  else { Note "자동 설치가 실패했습니다(사내망에서 winget 이 막혀 있을 수 있습니다). 사내 소프트웨어 센터를 이용하세요." }
}

# ── 1. 필요한 프로그램 ─────────────────────────────────────────────
Section "1. 필요한 프로그램"

if (Have 'git') { Ok ("git " + ((git --version) -split ' ')[2]) }
else { Bad "git 이 없습니다"; TryWinget 'Git.Git' 'Git' }

if (Have 'docker') { Ok ("docker " + (((docker --version) -split ' ')[2] -replace ',','')) }
else {
  Bad "docker 가 없습니다"
  Note "Docker Desktop 이 필요합니다. 사내 보안망에서는 보통 사내 소프트웨어 센터로 설치합니다."
  TryWinget 'Docker.DockerDesktop' 'Docker Desktop'
}

if (Have 'docker') {
  docker compose version 2>&1 | Out-Null
  if ($LASTEXITCODE -eq 0) { Ok ("docker compose " + (docker compose version --short 2>$null)) }
  else { Bad "docker compose(v2) 가 없습니다 — Docker Desktop 최신판에는 들어 있습니다" }

  docker info 2>&1 | Out-Null
  if ($LASTEXITCODE -eq 0) { Ok "도커가 실행 중입니다" }
  else {
    Bad "도커가 실행되고 있지 않습니다"
    Note "시작 메뉴에서 Docker Desktop 을 켜고, 고래 아이콘이 'Running' 이 된 뒤 다시 실행하세요."
    Note "(npipe... 오류가 바로 이 경우입니다)"
  }
}

# ── 2. 디스크 여유 ────────────────────────────────────────────────
Section "2. 디스크 여유"
try {
  $free = [math]::Floor((Get-PSDrive -Name (Get-Location).Drive.Name).Free / 1GB)
  if ($free -ge 15) { Ok "남은 공간 약 ${free}GB" } else { Warn "남은 공간 약 ${free}GB (이미지 빌드에 15GB 쯤 권장)" }
} catch { Warn "남은 공간을 확인하지 못했습니다" }

# ── 3. 설정 파일(.env) ────────────────────────────────────────────
Section "3. 설정 파일 (.env)"
if (-not (Test-Path .env)) {
  if ($Fix -and $Simple) {
    Copy-Item config/profiles/home.env.example .env
    Ok ".env 를 확인용(개발) 프로필로 만들었습니다 — 값을 안 채워도 그냥 뜹니다"
  } elseif ($Fix) {
    Copy-Item config/profiles/company.env.example .env
    Ok ".env 를 회사 프로필에서 만들었습니다"
    Note "메모장으로 열어서 값을 채운 뒤 이 스크립트를 다시 실행하세요."
  } else {
    Bad ".env 가 없습니다"
    Note "copy config\profiles\company.env.example .env   (또는 -Fix 옵션)"
  }
}

$envMap = @{}
if (Test-Path .env) {
  foreach ($line in (Get-Content .env -Encoding UTF8)) {
    if ($line -match '^\s*#') { continue }
    $i = $line.IndexOf('=')
    if ($i -gt 0) { $envMap[$line.Substring(0,$i).Trim()] = $line.Substring($i+1).Trim() }
  }
}
function Env2($k) { if ($envMap.ContainsKey($k)) { return $envMap[$k] } else { return '' } }

if (Test-Path .env) {
  $appEnv = Env2 'APP_ENV'
  if ($appEnv -eq 'production') { Ok "APP_ENV=production" }
  else {
    $script:DevMode = $true
    Ok ("APP_ENV='" + $(if ($appEnv) { $appEnv } else { 'dev' }) + "' — 확인용입니다. 아래 값들은 참고만 하세요")
    Note "실제로 사람들에게 열어 줄 때는 APP_ENV=production 으로 바꾸고 다시 점검하세요."
  }

  foreach ($pair in @(@('SECRET_KEY','반드시_바꾸세요'), @('ENCRYPTION_KEY','반드시_바꾸세요_다른값으로'))) {
    $k = $pair[0]; $sample = $pair[1]; $v = Env2 $k
    if (-not $v) {
      if ($k -eq 'ENCRYPTION_KEY') { Warn "$k 가 비어 있습니다 (SECRET_KEY 를 같이 씁니다)" } else { BadProd "$k 가 비어 있습니다" }
    } elseif ($v -eq $sample) {
      BadProd "$k 가 예시값 그대로입니다 — APP_ENV=production 이면 서버가 뜨지 않습니다"
      Note "만드는 법:  python -c ""import secrets;print(secrets.token_urlsafe(48))"""
    } elseif ($v.Length -lt 32) { Warn "$k 가 짧습니다($($v.Length)자). 32자 이상을 권합니다" }
    else { Ok "$k 채워져 있습니다" }
  }

  $cors = Env2 'CORS_ORIGINS'
  if ($cors -eq '*') { BadProd "CORS_ORIGINS=* 입니다 — 운영에서는 서버가 뜨지 않습니다" }
  elseif (-not $cors) { Warn "CORS_ORIGINS 가 비어 있습니다" }
  elseif ($cors -like '*사내서버주소*') { BadProd "CORS_ORIGINS 가 예시 주소 그대로입니다 — 실제 접속 주소로 바꾸세요" }
  else { Ok "CORS_ORIGINS=$cors" }

  $dha = Env2 'DEV_HEADER_AUTH'
  if ($dha -eq 'true') { BadProd "DEV_HEADER_AUTH=true 입니다 — 개발용 통로입니다. false 로 두세요" }
  else { Ok ("DEV_HEADER_AUTH=" + $(if ($dha) { $dha } else { 'false' })) }

  $apw = Env2 'ADMIN_PASSWORD'
  if (-not $apw) { Warn "ADMIN_PASSWORD 가 비어 있습니다 — 관리자 계정이 안 만들어집니다" }
  elseif ($apw -eq '여기에_비밀번호') { BadProd "ADMIN_PASSWORD 가 예시값 그대로입니다 (로그인 비밀번호가 그 글자 그대로가 됩니다)" }
  else { Ok "ADMIN_ID/ADMIN_PASSWORD 채워져 있습니다" }

  $apiBase = Env2 'NEXT_PUBLIC_API_BASE'
  if (-not $apiBase) { Warn "NEXT_PUBLIC_API_BASE 가 비어 있습니다 — 화면이 백엔드를 못 찾습니다" }
  elseif ($apiBase -like '*사내서버주소*') { BadProd "NEXT_PUBLIC_API_BASE 가 예시 주소 그대로입니다 — 사람들이 접속할 주소로 바꾸세요" }
  else { Ok "NEXT_PUBLIC_API_BASE=$apiBase" }

  $llm = Env2 'LLM_BASE_URL'
  if ((-not $llm) -or ($llm -like '*사내*')) { Warn "LLM_BASE_URL 이 아직 예시값입니다 — Gauss 주소를 넣기 전까지 '계획 세우기'만 안 됩니다" }
  else { Ok "LLM_BASE_URL=$llm" }
}

# ── 4. 사내 패키지 미러 ───────────────────────────────────────────
Section "4. 사내 패키지 미러 (폐쇄망이면 필수)"

function WebOk($url) {
  try { Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 10 | Out-Null; return $true } catch { return $false }
}

$pipIndex = Env2 'PIP_INDEX_URL'
if (-not $pipIndex) {
  if (WebOk 'https://pypi.org/simple/') { Ok "PIP_INDEX_URL 은 비었지만 pypi.org 에 바로 닿습니다" }
  else {
    Bad "PIP_INDEX_URL 이 비어 있고 pypi.org 에도 닿지 않습니다 — 빌드가 여기서 멈춥니다"
    Note ".env 에 사내 Nexus/Artifactory 주소를 넣으세요:"
    Note "  PIP_INDEX_URL=https://nexus.사내주소/repository/pypi/simple"
    Note "  PIP_TRUSTED_HOST=nexus.사내주소"
  }
} else {
  Ok "PIP_INDEX_URL=$pipIndex"
  # 필요한 패키지가 미러에 이름+버전으로 실제 있는지 확인합니다.
  # (cryptography 는 이번에 새로 들어온 것이라 미러에 없을 수 있습니다)
  $base = $pipIndex.TrimEnd('/')
  $reqs = @()
  foreach ($f in @('backend/requirements.txt','official_apps/requirements.txt')) {
    if (Test-Path $f) { $reqs += (Get-Content $f | ForEach-Object { ($_ -replace '#.*','').Trim() } | Where-Object { $_ -match '==' }) }
  }
  $missing = 0
  foreach ($r in $reqs) {
    $r = $r -replace '\[.*\]',''
    $name, $ver = $r -split '=='
    $norm = ($name.ToLower() -replace '[_\.]','-')
    try {
      $body = (Invoke-WebRequest -Uri "$base/$norm/" -UseBasicParsing -TimeoutSec 15).Content
      if ($body -notmatch [regex]::Escape("-$ver")) { Bad "$name==$ver 가 사내 미러에 없습니다"; $missing++ }
    } catch { Warn "$name — 미러 응답이 없습니다(확인 필요)"; $missing++ }
  }
  if ($missing -eq 0) { Ok "필요한 파이썬 패키지가 사내 미러에 모두 있습니다" }
  if (($pipIndex -like 'https://*') -and (-not (Env2 'PIP_TRUSTED_HOST'))) {
    Note "사내 인증서 때문에 막히면 PIP_TRUSTED_HOST 도 함께 넣으세요."
  }
}

$npmReg = Env2 'NPM_REGISTRY'
if ($npmReg) { Ok "NPM_REGISTRY=$npmReg" }
elseif (WebOk 'https://registry.npmjs.org/') { Ok "npm 공식 저장소에 바로 닿습니다" }
else { Bad "NPM_REGISTRY 가 비어 있고 registry.npmjs.org 에도 닿지 않습니다 — 화면(frontend) 빌드가 멈춥니다" }

# ── 5. 도커 기본 이미지 ───────────────────────────────────────────
Section "5. 도커 기본 이미지"
$images = @('python:3.11-slim','node:20-alpine','postgres:16-alpine','redis:7-alpine')
docker info 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
  foreach ($img in $images) {
    docker image inspect $img 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { Ok "$img (이미 받아 둠)" }
    elseif ($Deep) {
      docker pull -q $img 2>&1 | Out-Null
      if ($LASTEXITCODE -eq 0) { Ok "$img 내려받기 성공" }
      else {
        Bad "$img 를 받지 못했습니다 — 사내 레지스트리 미러 주소가 필요합니다"
        Note "각 Dockerfile 의 FROM 줄을 사내 주소로 바꾸거나, 도커 설정에 미러를 등록하세요."
      }
    } else { Warn "$img 아직 없음 (-Deep 을 붙이면 실제로 받아 봅니다)" }
  }
  if ($Deep -and $pipIndex) {
    Write-Host "  ... 사내 미러에서 cryptography 를 실제로 받아 보는 중"
    docker run --rm python:3.11-slim pip download --no-deps -d /tmp/x -i $pipIndex "cryptography==44.0.0" 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { Ok "사내 미러에서 cryptography==44.0.0 내려받기 성공" }
    else {
      Bad "사내 미러에서 cryptography==44.0.0 를 받지 못했습니다"
      Note "IT 에 'PyPI 미러에 cryptography 44.0.0 을 올려 달라'고 요청하세요."
    }
  }
} else { Warn "도커가 꺼져 있어 이미지 확인을 건너뜁니다" }

# ── 6. 포트 ───────────────────────────────────────────────────────
Section "6. 포트 비어 있나"
$ports = @(3000,8000,9001,9101,9102,9103,9111,9112,9113,9114,9115,9116,9117)
$busy = @()
foreach ($p in $ports) {
  try { if (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue) { $busy += $p } } catch {}
}
if ($busy.Count -eq 0) { Ok "쓰는 포트 13개가 모두 비어 있습니다" }
else { Warn ("이미 쓰는 중인 포트: " + ($busy -join ' ') + " (이전에 띄워 둔 것이면 괜찮습니다)") }

# ── 마무리 ────────────────────────────────────────────────────────
Write-Host ""
Write-Host "────────────────────────────────────────"
Write-Host ("  통과 {0} · 주의 {1} · 막힘 {2}" -f $script:Pass, $script:Warn, $script:Fail)
if ($script:Fail -gt 0) {
  Write-Host "  [막힘] 을 먼저 해결하세요. 그대로 두면 기동 중에 멈춥니다." -ForegroundColor Red
  Write-Host ""
  exit 1
}
Write-Host "  다음 단계:  docker compose up -d --build"
Write-Host "  띄운 뒤   :  powershell -ExecutionPolicy Bypass -File scripts\check_running.ps1"
Write-Host ""
