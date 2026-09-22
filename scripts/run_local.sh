#!/usr/bin/env bash
# 도커 없이 띄웁니다. 회사 PC 에 Docker Desktop 을 못 까는 경우를 위한 길입니다.
#
#   bash scripts/run_local.sh          # 띄우기
#   bash scripts/stop_local.sh         # 내리기
#
# 필요한 것: Python 3.11 이상, Node 20 이상. 그 둘만 있으면 됩니다.
# 데이터베이스는 PostgreSQL 대신 SQLite 파일 하나를 씁니다(.local-run/app.db).
#
# 되는 것   : 로그인, 앱스토어, 대시보드, 도구, 공식 앱 11개, 양식·보고서
# 안 되는 것: "계획 세우기"(오케스트레이터). Redis 가 필요합니다.
#             어차피 Gauss(LLM) 주소가 없으면 이 기능은 도커로 띄워도 안 됩니다.
set -u

cd "$(dirname "$0")/.." || exit 1
ROOT=$(pwd)
RUN_DIR="$ROOT/.local-run"
VENV="$ROOT/.venv-local"

ok()   { printf '  [ OK ] %s\n' "$*"; }
bad()  { printf '  [안됨] %s\n' "$*"; }
note() { printf '         %s\n' "$*"; }
head_() { printf '\n== %s ==\n' "$*"; }
die()  { printf '\n  [막힘] %s\n\n' "$*"; exit 1; }

getenv() { [ -f "$ROOT/.env" ] || return 0; sed -n "s/^$1=//p" "$ROOT/.env" | tail -1 | tr -d '\r'; }

# ── 1. 파이썬·노드 ──────────────────────────────────────────────────
head_ "1. 필요한 프로그램"

PY=""
for c in python3.13 python3.12 python3.11 python3 python; do
  command -v "$c" >/dev/null 2>&1 || continue
  v=$("$c" -c 'import sys;print(sys.version_info[0]*100+sys.version_info[1])' 2>/dev/null)
  if [ -n "$v" ] && [ "$v" -ge 311 ]; then PY="$c"; break; fi
done
[ -n "$PY" ] || die "Python 3.11 이상이 없습니다. 사내 소프트웨어 센터에서 설치하세요."
ok "python $($PY --version 2>&1 | awk '{print $2}')"

command -v node >/dev/null 2>&1 || die "Node.js 가 없습니다. 20 이상을 설치하세요(화면을 띄우는 데 씁니다)."
NODE_MAJOR=$(node --version | sed 's/^v//' | cut -d. -f1)
[ "$NODE_MAJOR" -ge 20 ] || die "Node $NODE_MAJOR 입니다. 20 이상이 필요합니다."
ok "node $(node --version)"

# ── 2. 파이썬 꾸러미 ────────────────────────────────────────────────
head_ "2. 파이썬 꾸러미"
PIP_ARGS=""
PIP_INDEX_URL=$(getenv PIP_INDEX_URL)
PIP_TRUSTED_HOST=$(getenv PIP_TRUSTED_HOST)
[ -n "$PIP_INDEX_URL" ] && PIP_ARGS="$PIP_ARGS -i $PIP_INDEX_URL"
[ -n "$PIP_TRUSTED_HOST" ] && PIP_ARGS="$PIP_ARGS --trusted-host $PIP_TRUSTED_HOST"

if [ ! -x "$VENV/bin/python" ]; then
  printf '  ... 파이썬 전용 방(venv)을 만드는 중\n'
  "$PY" -m venv "$VENV" || die "venv 를 만들지 못했습니다."
fi
if [ ! -f "$RUN_DIR/.deps-ok" ]; then
  printf '  ... 꾸러미를 받는 중 (처음 한 번, 몇 분 걸립니다)\n'
  # shellcheck disable=SC2086
  "$VENV/bin/pip" install -q --upgrade pip $PIP_ARGS >/dev/null 2>&1
  # shellcheck disable=SC2086
  if ! "$VENV/bin/pip" install -q $PIP_ARGS \
        -r backend/requirements.txt \
        -r official_apps/requirements.txt \
        -r official_apps/mail/requirements.txt; then
    note "사내망이면 .env 에 PIP_INDEX_URL / PIP_TRUSTED_HOST 를 넣고 다시 실행하세요."
    die "파이썬 꾸러미를 받지 못했습니다."
  fi
  mkdir -p "$RUN_DIR" && : > "$RUN_DIR/.deps-ok"
fi
ok "파이썬 꾸러미 준비됨 ($VENV)"

# ── 3. 자리 만들기 ──────────────────────────────────────────────────
head_ "3. 자리 만들기"
mkdir -p "$RUN_DIR/data" "$RUN_DIR/logs"
: > "$RUN_DIR/pids"

# 앱 목록의 주소는 도커용 이름(app-mail 등)이라 그대로는 못 찾습니다.
# 도커 없이 띄울 때는 전부 127.0.0.1 로 바꾼 사본을 만들어 씁니다.
SEED_LOCAL="$RUN_DIR/apps.seed.local.json"
"$VENV/bin/python" - "$ROOT" "$SEED_LOCAL" <<'PY'
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
        # http://app-mail:9101/mcp  ->  http://127.0.0.1:9101/mcp
        app["endpoint"] = re.sub(r"^http://[^/:]+:", "http://127.0.0.1:", endpoint)
        apps.append(app)
out.write_text(json.dumps({"apps": apps}, ensure_ascii=False, indent=2), encoding="utf-8")
msg = f"  [ OK ] 앱 목록 {len(apps)}개를 localhost 주소로 바꿔 두었습니다"
if skipped:
    msg += f" (여기서 안 띄우는 앱 {skipped}개는 뺐습니다)"
print(msg)
PY
[ -f "$SEED_LOCAL" ] || die "앱 목록 파일을 만들지 못했습니다."

start() {  # start <이름> <작업폴더> <로그이름> -- <명령...>
  name=$1; dir=$2; shift 2
  ( cd "$ROOT/$dir" && "$@" >"$RUN_DIR/logs/$name.log" 2>&1 & echo $! >>"$RUN_DIR/pids" )
}

wait_port() {  # wait_port <포트> <몇초까지>
  p=$1; limit=${2:-30}; i=0
  while [ "$i" -lt "$limit" ]; do
    if "$VENV/bin/python" -c "import socket,sys; s=socket.socket(); s.settimeout(1); sys.exit(0 if s.connect_ex(('127.0.0.1',$p))==0 else 1)" 2>/dev/null; then
      return 0
    fi
    i=$((i+1)); sleep 1
  done
  return 1
}

# ── 4. 공식 앱 11개 ─────────────────────────────────────────────────
head_ "4. 공식 앱 11개"
export DATA_DIR="$RUN_DIR/data"
export PYTHONUNBUFFERED=1

# 업무 도구 앱 8개: official_apps/ 폴더에서 패키지로 띄웁니다.
for pair in "9111 dev_projects" "9112 achievements" "9113 weekly_report" \
            "9114 toolbox" "9115 meeting_scheduler" "9116 approvals" "9117 docs_assistant" "9118 report_forms"; do
  port=${pair%% *}; pkg=${pair##* }
  PORT="$port" PUBLIC_BASE_URL="http://localhost:$port" \
    start "$pkg" official_apps "$VENV/bin/python" -m "$pkg.server"
done

# 시나리오 앱 3개: 자기 폴더 안에서 mcp_adapter 를 읽으므로 그 폴더에서 띄웁니다.
PORT=9101 MAIL_DB="$RUN_DIR/data/mail.db" MAIL_ADAPTER=mock \
  start mail official_apps/mail "$VENV/bin/python" server.py
PORT=9102 MEETING_DB="$RUN_DIR/data/meeting.db" \
  start meeting official_apps/meeting "$VENV/bin/python" server.py
PORT=9103 TASKS_DB="$RUN_DIR/data/tasks.db" \
  start tasks official_apps/tasks "$VENV/bin/python" server.py

failed=""
for p in 9101 9102 9103 9111 9112 9113 9114 9115 9116 9117 9118; do
  wait_port "$p" 30 || failed="$failed $p"
done
if [ -n "$failed" ]; then
  bad "안 뜬 앱 포트:$failed"
  note "이유는 여기에 있습니다: .local-run/logs/"
else
  ok "공식 앱 11개가 떴습니다 (9101~9103, 9111~9118)"
fi

# ── 5. 백엔드 ───────────────────────────────────────────────────────
head_ "5. 백엔드"
# 앱이 다 뜬 뒤에 띄웁니다. 먼저 띄우면 기능 목록을 못 읽고 그대로 굳습니다.
ADMIN_ID=$(getenv ADMIN_ID); [ -n "$ADMIN_ID" ] || ADMIN_ID=admin
ADMIN_PASSWORD=$(getenv ADMIN_PASSWORD)
case "${ADMIN_PASSWORD:-}" in ""|여기에_비밀번호) ADMIN_PASSWORD="local-check-1234" ;; esac

APP_ENV=dev \
DATABASE_URL="sqlite:///$RUN_DIR/app.db" \
DATA_DIR="$RUN_DIR/data" \
SEED_FILE="$SEED_LOCAL" \
SECRET_KEY="local-only-$(date +%s)-도커없이확인용-32자이상" \
ADMIN_ID="$ADMIN_ID" ADMIN_PASSWORD="$ADMIN_PASSWORD" \
DEV_HEADER_AUTH=false CORS_ORIGINS="http://localhost:3000" \
SCHEDULER_ENABLED=false HEALTHCHECK_INTERVAL_SECONDS=0 \
  start backend backend "$VENV/bin/python" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 확인 스크립트(check_running)가 로그인해 볼 수 있게 남겨 둡니다.
# 도커 없이 띄울 때는 .env 가 없을 수 있어서입니다.
printf 'ADMIN_ID=%s\nADMIN_PASSWORD=%s\n' "$ADMIN_ID" "$ADMIN_PASSWORD" > "$RUN_DIR/creds"

if wait_port 8000 40; then
  ok "백엔드가 떴습니다 (http://localhost:8000)"
else
  bad "백엔드가 안 떴습니다 — .local-run/logs/backend.log 를 보세요"
  tail -5 "$RUN_DIR/logs/backend.log" 2>/dev/null | sed 's/^/           /'
fi

# ── 6. 화면 ─────────────────────────────────────────────────────────
head_ "6. 화면"
if [ ! -d frontend/node_modules ]; then
  printf '  ... 화면 꾸러미를 받는 중 (처음 한 번, 1~3분)\n'
  NPM_REGISTRY=$(getenv NPM_REGISTRY)
  REG_ARG=""
  [ -n "$NPM_REGISTRY" ] && REG_ARG="--registry=$NPM_REGISTRY"
  # shellcheck disable=SC2086
  if ! ( cd frontend && npm install --no-audit --no-fund $REG_ARG >"$RUN_DIR/logs/npm-install.log" 2>&1 ); then
    bad "화면 꾸러미를 받지 못했습니다 — .local-run/logs/npm-install.log"
    note "사내망이면 .env 에 NPM_REGISTRY 를 넣고 다시 실행하세요."
  fi
fi

if [ -d frontend/node_modules ]; then
  # next start 가 아니라 dev 로 띄웁니다(빌드 없이 바로 뜨고, 확인용으로 충분합니다).
  NEXT_PUBLIC_API_BASE=http://localhost:8000 \
  NEXT_PUBLIC_MAIL_API=http://localhost:9101 \
  NEXT_PUBLIC_TASKS_API=http://localhost:9103 \
    start frontend frontend npx next dev -p 3000
  if wait_port 3000 90; then ok "화면이 떴습니다 (http://localhost:3000)"
  else bad "화면이 안 떴습니다 — .local-run/logs/frontend.log 를 보세요"; fi
fi

# ── 마무리 ──────────────────────────────────────────────────────────
printf '\n────────────────────────────────────────\n'
printf '  브라우저에서  http://localhost:3000\n'
printf '  로그인       사번 %s / 비밀번호 %s\n' "$ADMIN_ID" "$ADMIN_PASSWORD"
printf '  확인하기     bash scripts/check_running.sh\n'
printf '  내리기       bash scripts/stop_local.sh\n'
printf '  기록         .local-run/logs/\n\n'
printf '  ※ "계획 세우기"는 Redis 가 없어 안 됩니다. 나머지 화면은 다 됩니다.\n\n'
