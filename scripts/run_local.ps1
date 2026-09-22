<#
  도커 없이 띄웁니다. 회사 PC 에 Docker Desktop 을 못 까는 경우를 위한 길입니다.
  (Docker Desktop 은 WSL2 나 Hyper-V 가 있어야 하는데, 사내 정책으로 막혀 있으면 설치해도 못 씁니다.)

    powershell -ExecutionPolicy Bypass -File scripts\run_local.ps1     # 띄우기
    powershell -ExecutionPolicy Bypass -File scripts\stop_local.ps1    # 내리기

  필요한 것: Python 3.11 이상, Node 20 이상. 그 둘만 있으면 됩니다.
  데이터베이스는 PostgreSQL 대신 SQLite 파일 하나를 씁니다(.local-run\app.db).

  되는 것   : 로그인, 앱스토어, 대시보드, 도구, 공식 앱 11개, 양식·보고서
  안 되는 것: "계획 세우기"(오케스트레이터). Redis 가 필요합니다.
              어차피 Gauss(LLM) 주소가 없으면 이 기능은 도커로 띄워도 안 됩니다.
#>
param(
  [switch]$Reinstall   # 꾸러미를 처음부터 다시 받습니다
)

$ErrorActionPreference = 'Continue'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

Set-Location (Split-Path $PSScriptRoot -Parent)
$Root   = (Get-Location).Path
$RunDir = Join-Path $Root '.local-run'
$Venv   = Join-Path $Root '.venv-local'
$VenvPy = Join-Path $Venv 'Scripts\python.exe'

function Ok($m)   { Write-Host "  [ OK ] $m" -ForegroundColor Green }
function Bad($m)  { Write-Host "  [안됨] $m" -ForegroundColor Red }
function Note($m) { Write-Host "         $m" -ForegroundColor DarkGray }
function Section($m) { Write-Host ""; Write-Host "== $m ==" -ForegroundColor Cyan }
function Die($m)  { Write-Host ""; Write-Host "  [막힘] $m" -ForegroundColor Red; Write-Host ""; exit 1 }

$envMap = @{}
$envPath = Join-Path $Root '.env'
if (Test-Path $envPath) {
  foreach ($line in (Get-Content $envPath -Encoding UTF8)) {
    if ($line -match '^\s*#') { continue }
    $i = $line.IndexOf('='); if ($i -gt 0) { $envMap[$line.Substring(0,$i).Trim()] = $line.Substring($i+1).Trim() }
  }
}
function Env2($k) { if ($envMap.ContainsKey($k)) { return $envMap[$k] } else { return '' } }

# ── 1. 필요한 프로그램 ─────────────────────────────────────────────
Section "1. 필요한 프로그램"

$py = $null
foreach ($c in @('python','python3','py')) {
  $cmd = Get-Command $c -ErrorAction SilentlyContinue
  if (-not $cmd) { continue }
  $v = & $c -c "import sys;print(sys.version_info[0]*100+sys.version_info[1])" 2>$null
  if ($v -and [int]$v -ge 311) { $py = $c; break }
}
if (-not $py) { Die "Python 3.11 이상이 없습니다. 사내 소프트웨어 센터에서 설치하세요 (설치할 때 'Add to PATH' 를 켜세요)." }
Ok ("python " + (& $py --version 2>&1))

if (-not (Get-Command node -ErrorAction SilentlyContinue)) { Die "Node.js 가 없습니다. 20 이상을 설치하세요(화면을 띄우는 데 씁니다)." }
$nodeMajor = [int]((node --version) -replace '^v','' -split '\.')[0]
if ($nodeMajor -lt 20) { Die "Node $nodeMajor 입니다. 20 이상이 필요합니다." }
Ok ("node " + (node --version))

# ── 2. 파이썬 꾸러미 ───────────────────────────────────────────────
Section "2. 파이썬 꾸러미"
$pipArgs = @()
if (Env2 'PIP_INDEX_URL')   { $pipArgs += @('-i', (Env2 'PIP_INDEX_URL')) }
if (Env2 'PIP_TRUSTED_HOST'){ $pipArgs += @('--trusted-host', (Env2 'PIP_TRUSTED_HOST')) }

# -Reinstall 은 venv 뿐 아니라 '받아 뒀음' 표시도 지워야 합니다.
# 표시가 남아 있으면 새로 만든 빈 venv 에 꾸러미를 안 넣고 지나갑니다.
if ($Reinstall) {
  if (Test-Path $Venv) { Remove-Item -Recurse -Force $Venv }
  Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $RunDir '.deps-ok')
}
if (-not (Test-Path $VenvPy)) {
  Write-Host "  ... 파이썬 전용 방(venv)을 만드는 중"
  & $py -m venv $Venv
  if (-not (Test-Path $VenvPy)) { Die "venv 를 만들지 못했습니다." }
}
# 받아 둔 꾸러미가 지금 목록과 같은지 봅니다. 그냥 "한 번 받았음" 표시만 남기면,
# 나중에 requirements 에 꾸러미가 하나 늘었을 때 조용히 건너뛰어서
# "회사에서 갑자기 앱이 안 뜬다" 가 됩니다.
$depsMark = Join-Path $RunDir '.deps-ok'
$reqFiles = @('backend/requirements.txt', 'official_apps/requirements.txt', 'official_apps/mail/requirements.txt')
$depsFp = (($reqFiles | ForEach-Object { (Get-FileHash -Path (Join-Path $Root $_) -Algorithm SHA256).Hash }) -join '-')
$depsHave = ''
if (Test-Path $depsMark) { $depsHave = ((Get-Content $depsMark -Raw -ErrorAction SilentlyContinue) + '').Trim() }
if ($depsHave -ne $depsFp) {
  Write-Host "  ... 꾸러미를 받는 중 (처음 한 번, 몇 분 걸립니다)"
  & $VenvPy -m pip install -q --upgrade pip @pipArgs 2>&1 | Out-Null
  & $VenvPy -m pip install -q @pipArgs `
      -r backend/requirements.txt `
      -r official_apps/requirements.txt `
      -r official_apps/mail/requirements.txt
  if ($LASTEXITCODE -ne 0) {
    Note "사내망이면 .env 에 PIP_INDEX_URL / PIP_TRUSTED_HOST 를 넣고 다시 실행하세요."
    Die "파이썬 꾸러미를 받지 못했습니다."
  }
  New-Item -ItemType Directory -Force -Path $RunDir | Out-Null
  Set-Content -Path $depsMark -Value $depsFp -Encoding ascii
}
Ok "파이썬 꾸러미 준비됨 ($Venv)"

# ── 3. 자리 만들기 ─────────────────────────────────────────────────
Section "3. 자리 만들기"
New-Item -ItemType Directory -Force -Path (Join-Path $RunDir 'data') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $RunDir 'logs') | Out-Null
$PidFile = Join-Path $RunDir 'pids'
Set-Content -Path $PidFile -Value '' -Encoding ascii

# 앱 목록의 주소는 도커용 이름(app-mail 등)이라 그대로는 못 찾습니다.
# 도커 없이 띄울 때는 전부 127.0.0.1 로 바꾼 사본을 만들어 씁니다.
$SeedLocal = Join-Path $RunDir 'apps.seed.local.json'
$mkSeed = Join-Path $RunDir '_mkseed.py'
@'
import json, re, sys
from pathlib import Path

root, out = Path(sys.argv[1]), Path(sys.argv[2])

# 이 스크립트가 실제로 띄우는 포트들만 남깁니다. 안 띄우는 앱(예시 어댑터 등)을
# 그대로 두면 앱스토어에 "응답 없음"으로 뜨는데, 고장난 것처럼 보입니다.
RUNNING = {"9101", "9102", "9103", "9111", "9112", "9113", "9114", "9115", "9116", "9117", "9118"}

apps, skipped = [], 0
for name in ("apps.seed.official.json", "apps.seed.example.json", "apps.seed.json"):
    path = root / "config" / name
    if not path.exists():
        continue
    for app in json.loads(path.read_text(encoding="utf-8")).get("apps", []):
        endpoint = app.get("endpoint", "")
        port = re.search(r":(\d+)", endpoint)
        if not port or port.group(1) not in RUNNING:
            skipped += 1
            continue
        app["endpoint"] = re.sub(r"^http://[^/:]+:", "http://127.0.0.1:", endpoint)
        apps.append(app)
out.write_text(json.dumps({"apps": apps}, ensure_ascii=False, indent=2), encoding="utf-8")
msg = f"  [ OK ] 앱 목록 {len(apps)}개를 localhost 주소로 바꿔 두었습니다"
if skipped:
    msg += f" (여기서 안 띄우는 앱 {skipped}개는 뺐습니다)"
print(msg)
'@ | Set-Content -Path $mkSeed -Encoding UTF8
& $VenvPy $mkSeed $Root $SeedLocal
if (-not (Test-Path $SeedLocal)) { Die "앱 목록 파일을 만들지 못했습니다." }

function Start-Part {
  param([string]$Name, [string]$Dir, [string]$Exe, [string[]]$ArgList, [hashtable]$EnvVars)
  $old = @{}
  foreach ($k in $EnvVars.Keys) { $old[$k] = [Environment]::GetEnvironmentVariable($k); [Environment]::SetEnvironmentVariable($k, $EnvVars[$k]) }
  $log = Join-Path $RunDir "logs\$Name.log"
  $p = Start-Process -FilePath $Exe -ArgumentList $ArgList -WorkingDirectory (Join-Path $Root $Dir) `
         -WindowStyle Hidden -PassThru -RedirectStandardOutput $log -RedirectStandardError "$log.err"
  Add-Content -Path $PidFile -Value $p.Id
  foreach ($k in $EnvVars.Keys) { [Environment]::SetEnvironmentVariable($k, $old[$k]) }
  return $p
}

function Wait-Port([int]$Port, [int]$Seconds = 30) {
  for ($i = 0; $i -lt $Seconds; $i++) {
    try {
      $c = New-Object Net.Sockets.TcpClient
      $c.Connect('127.0.0.1', $Port); $c.Close(); return $true
    } catch { Start-Sleep -Seconds 1 }
  }
  return $false
}

# ── 4. 공식 앱 11개 ────────────────────────────────────────────────
Section "4. 공식 앱 11개"
$dataDir = Join-Path $RunDir 'data'

# 업무 도구 앱 8개: official_apps\ 폴더에서 패키지로 띄웁니다.
foreach ($pair in @(@(9111,'dev_projects'), @(9112,'achievements'), @(9113,'weekly_report'),
                    @(9114,'toolbox'), @(9115,'meeting_scheduler'), @(9116,'approvals'), @(9117,'docs_assistant'), @(9118,'report_forms'))) {
  $port = $pair[0]; $pkg = $pair[1]
  Start-Part -Name $pkg -Dir 'official_apps' -Exe $VenvPy -ArgList @('-m', "$pkg.server") -EnvVars @{
    PORT = "$port"; DATA_DIR = $dataDir; PUBLIC_BASE_URL = "http://localhost:$port"; PYTHONUNBUFFERED = '1'
  } | Out-Null
}

# 시나리오 앱 3개: 자기 폴더 안에서 mcp_adapter 를 읽으므로 그 폴더에서 띄웁니다.
Start-Part -Name 'mail' -Dir 'official_apps\mail' -Exe $VenvPy -ArgList @('server.py') -EnvVars @{
  PORT = '9101'; MAIL_DB = (Join-Path $dataDir 'mail.db'); MAIL_ADAPTER = 'mock'; DATA_DIR = $dataDir; PYTHONUNBUFFERED = '1'
} | Out-Null
Start-Part -Name 'meeting' -Dir 'official_apps\meeting' -Exe $VenvPy -ArgList @('server.py') -EnvVars @{
  PORT = '9102'; MEETING_DB = (Join-Path $dataDir 'meeting.db'); DATA_DIR = $dataDir; PYTHONUNBUFFERED = '1'
} | Out-Null
Start-Part -Name 'tasks' -Dir 'official_apps\tasks' -Exe $VenvPy -ArgList @('server.py') -EnvVars @{
  PORT = '9103'; TASKS_DB = (Join-Path $dataDir 'tasks.db'); DATA_DIR = $dataDir; PYTHONUNBUFFERED = '1'
} | Out-Null

$failed = @()
foreach ($p in @(9101,9102,9103,9111,9112,9113,9114,9115,9116,9117,9118)) {
  if (-not (Wait-Port $p 30)) { $failed += $p }
}
if ($failed.Count -eq 0) { Ok "공식 앱 11개가 떴습니다 (9101~9103, 9111~9118)" }
else {
  Bad ("안 뜬 앱 포트: " + ($failed -join ' '))
  Note "이유는 여기에 있습니다: .local-run\logs\"
}

# ── 5. 백엔드 ──────────────────────────────────────────────────────
Section "5. 백엔드"
# 앱이 다 뜬 뒤에 띄웁니다. 먼저 띄우면 기능 목록을 못 읽고 그대로 굳습니다.
$adminId = Env2 'ADMIN_ID';       if (-not $adminId) { $adminId = 'admin' }
$adminPw = Env2 'ADMIN_PASSWORD'; if ((-not $adminPw) -or ($adminPw -eq '여기에_비밀번호')) { $adminPw = 'local-check-1234' }

Start-Part -Name 'backend' -Dir 'backend' -Exe $VenvPy `
  -ArgList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000') -EnvVars @{
    APP_ENV = 'dev'
    DATABASE_URL = ("sqlite:///" + (Join-Path $RunDir 'app.db') -replace '\\','/')
    DATA_DIR = $dataDir
    SEED_FILE = $SeedLocal
    SECRET_KEY = ('local-only-' + [guid]::NewGuid().ToString() + '-도커없이확인용')
    ADMIN_ID = $adminId
    ADMIN_PASSWORD = $adminPw
    DEV_HEADER_AUTH = 'false'
    CORS_ORIGINS = 'http://localhost:3000'
    SCHEDULER_ENABLED = 'false'
    HEALTHCHECK_INTERVAL_SECONDS = '0'
    PYTHONUNBUFFERED = '1'
  } | Out-Null

# 확인 스크립트(check_running)가 로그인해 볼 수 있게 남겨 둡니다.
# 도커 없이 띄울 때는 .env 가 없을 수 있어서입니다.
Set-Content -Path (Join-Path $RunDir 'creds') -Value "ADMIN_ID=$adminId`nADMIN_PASSWORD=$adminPw" -Encoding UTF8

if (Wait-Port 8000 40) { Ok "백엔드가 떴습니다 (http://localhost:8000)" }
else {
  Bad "백엔드가 안 떴습니다 — .local-run\logs\backend.log 를 보세요"
  $bl = Join-Path $RunDir 'logs\backend.log.err'
  if (Test-Path $bl) { Get-Content $bl -Tail 5 | ForEach-Object { Write-Host "           $_" } }
}

# ── 6. 화면 ────────────────────────────────────────────────────────
Section "6. 화면"
if (-not (Test-Path 'frontend\node_modules')) {
  Write-Host "  ... 화면 꾸러미를 받는 중 (처음 한 번, 1~3분)"
  $regArg = ''
  if (Env2 'NPM_REGISTRY') { $regArg = "--registry=" + (Env2 'NPM_REGISTRY') }
  $npmLog = Join-Path $RunDir 'logs\npm-install.log'
  Start-Process -FilePath 'cmd.exe' -ArgumentList @('/c', "npm install --no-audit --no-fund $regArg") `
    -WorkingDirectory (Join-Path $Root 'frontend') -WindowStyle Hidden -Wait `
    -RedirectStandardOutput $npmLog -RedirectStandardError "$npmLog.err"
  if (-not (Test-Path 'frontend\node_modules')) {
    Bad "화면 꾸러미를 받지 못했습니다 — .local-run\logs\npm-install.log"
    Note "사내망이면 .env 에 NPM_REGISTRY 를 넣고 다시 실행하세요."
  }
}

if (Test-Path 'frontend\node_modules') {
  # next start 가 아니라 dev 로 띄웁니다(빌드 없이 바로 뜨고, 확인용으로 충분합니다).
  Start-Part -Name 'frontend' -Dir 'frontend' -Exe 'cmd.exe' -ArgList @('/c','npx next dev -p 3000') -EnvVars @{
    NEXT_PUBLIC_API_BASE = 'http://localhost:8000'
    NEXT_PUBLIC_MAIL_API = 'http://localhost:9101'
    NEXT_PUBLIC_TASKS_API = 'http://localhost:9103'
  } | Out-Null
  if (Wait-Port 3000 90) { Ok "화면이 떴습니다 (http://localhost:3000)" }
  else { Bad "화면이 안 떴습니다 — .local-run\logs\frontend.log 를 보세요" }
}

# ── 마무리 ─────────────────────────────────────────────────────────
Write-Host ""
Write-Host "────────────────────────────────────────"
Write-Host "  브라우저에서  http://localhost:3000"
Write-Host "  로그인       사번 $adminId / 비밀번호 $adminPw"
Write-Host "  확인하기     powershell -ExecutionPolicy Bypass -File scripts\check_running.ps1"
Write-Host "  내리기       powershell -ExecutionPolicy Bypass -File scripts\stop_local.ps1"
Write-Host "  기록         .local-run\logs\"
Write-Host ""
Write-Host "  ※ `"계획 세우기`"는 Redis 가 없어 안 됩니다. 나머지 화면은 다 됩니다." -ForegroundColor DarkGray
Write-Host ""
