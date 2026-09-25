#!/usr/bin/env bash
# 띄운 "뒤에" 제대로 떴는지 확인합니다.
#
#   bash scripts/check_running.sh
#   bash scripts/check_running.sh --host http://사내서버주소
#
# 맥/리눅스용입니다. Windows 면 scripts/check_running.ps1 을 쓰세요.
set -u

cd "$(dirname "$0")/.." || exit 1

HOST="http://localhost"
while [ $# -gt 0 ]; do
  case "$1" in
    --host) HOST="${2%/}"; shift 2 ;;
    *) echo "모르는 옵션: $1"; exit 2 ;;
  esac
done

API="$HOST:8000"
WEB="$HOST:3000"

PASS=0; FAIL=0
ok()   { printf '  [ OK ] %s\n' "$*"; PASS=$((PASS+1)); }
bad()  { printf '  [안됨] %s\n' "$*"; FAIL=$((FAIL+1)); }
note() { printf '         %s\n' "$*"; }
head_() { printf '\n== %s ==\n' "$*"; }

# .env 가 없으면 도커 없이 띄운 기록에서 찾습니다(scripts/run_local.sh 가 남깁니다).
ENV_FILE=.env
[ -f "$ENV_FILE" ] || ENV_FILE=.local-run/creds
LOCAL_MODE=0
[ "$ENV_FILE" = ".local-run/creds" ] && [ -f "$ENV_FILE" ] && LOCAL_MODE=1
getenv() { [ -f "$ENV_FILE" ] || return 0; sed -n "s/^$1=//p" "$ENV_FILE" | tail -1 | tr -d '\r'; }

# ── 1. 컨테이너 ─────────────────────────────────────────────────────
head_ "1. 컨테이너가 다 떴나"
if [ "$LOCAL_MODE" = 1 ]; then
  note "도커 없이 띄운 모드입니다(.local-run/). 컨테이너 점검은 건너뜁니다."
elif docker compose ps --format '{{.Service}} {{.State}}' >/tmp/_wfa_ps 2>/dev/null; then
  total=$(wc -l </tmp/_wfa_ps | tr -d ' ')
  downs=$(grep -v ' running' /tmp/_wfa_ps || true)
  if [ -z "$downs" ]; then ok "서비스 ${total}개가 모두 running"
  else
    bad "떠 있지 않은 서비스가 있습니다:"
    printf '%s\n' "$downs" | sed 's/^/           /'
    note "docker compose logs --tail=50 <서비스이름>  으로 이유를 보세요."
  fi
  rm -f /tmp/_wfa_ps
else
  bad "docker compose ps 가 실패했습니다 — 도커가 켜져 있고 저장소 폴더에서 실행했는지 보세요"
  note "도커를 안 쓰는 PC 라면 bash scripts/run_local.sh 로 띄우세요."
fi

# ── 2. 백엔드 ───────────────────────────────────────────────────────
head_ "2. 백엔드 ($API)"
HEALTH=$(curl -sS --max-time 15 "$API/health" 2>/dev/null)
if [ -z "$HEALTH" ]; then
  bad "$API/health 에 닿지 않습니다"
  note "docker compose logs --tail=50 backend   — 설정 점검에 걸려 안 떴을 수 있습니다."
else
  case "$HEALTH" in
    *'"status":"ok"'*) ok "백엔드 정상 (DB·Redis 연결됨)" ;;
    *)
      if [ "$LOCAL_MODE" = 1 ] && ! printf '%s' "$HEALTH" | tr ',' '\n' | grep -i 'error' | grep -qv redis; then
        ok "백엔드 정상 (DB 연결됨. Redis 는 도커 없이 띄울 때 안 씁니다)"
      else
        bad "백엔드는 떴지만 일부가 안 됩니다:"
        printf '%s' "$HEALTH" | tr ',' '\n' | grep -i 'error' | tr -d '"{}' | sed 's/^/           /'
      fi
      ;;
  esac
  printf '           %s\n' "$(printf '%s' "$HEALTH" | tr ',' '\n' | grep -i 'llm_' | tr -d '"{}' | tr '\n' ' ')"
fi

# ── 3. 화면 ─────────────────────────────────────────────────────────
head_ "3. 화면 ($WEB)"
CODE=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "$WEB" 2>/dev/null)
[ "$CODE" = "200" ] && ok "화면이 열립니다 — 브라우저로 $WEB 접속하세요" \
  || bad "화면이 안 열립니다 (HTTP ${CODE:-응답없음}) — docker compose logs --tail=50 frontend"

# ── 4. 로그인 ───────────────────────────────────────────────────────
head_ "4. 로그인"
AID=$(getenv ADMIN_ID); APW=$(getenv ADMIN_PASSWORD)
TOKEN=""
if [ -z "$AID" ] || [ -z "$APW" ]; then
  bad "ADMIN_ID / ADMIN_PASSWORD 를 찾지 못해 로그인 확인을 못 합니다 (.env 또는 .local-run/creds)"
else
  RESP=$(curl -sS --max-time 15 -X POST "$API/api/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"user_id\":\"$AID\",\"password\":\"$APW\"}" 2>/dev/null)
  TOKEN=$(printf '%s' "$RESP" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')
  if [ -n "$TOKEN" ]; then
    ok "관리자($AID) 로그인 성공"
  else
    bad "로그인 실패: ${RESP:-응답없음}"
    note "계정은 '처음 기동할 때' 만들어집니다. .env 의 비밀번호만 나중에 바꾸면 반영되지 않습니다."
    note "ADMIN_RESET_PASSWORD=true 로 두고 docker compose restart backend 하면 덮어씁니다."
  fi
fi

# ── 5. 앱스토어 ─────────────────────────────────────────────────────
head_ "5. 앱스토어에 앱이 올라왔나"
if [ -n "$TOKEN" ]; then
  APPS=$(curl -sS --max-time 20 "$API/api/apps" -H "Authorization: Bearer $TOKEN" 2>/dev/null)
  N=$(printf '%s' "$APPS" | grep -o '"slug"' | wc -l | tr -d ' ')
  if [ "${N:-0}" -gt 0 ]; then
    ok "앱 ${N}개가 등록되어 있습니다"
    DOWN=$(printf '%s' "$APPS" | tr '}' '\n' | grep '"status":"unreachable"' \
           | sed -n 's/.*"name":"\([^"]*\)".*/\1/p' | tr '\n' ' ')
    [ -z "$DOWN" ] && ok "응답 안 하는 앱 없음" || bad "응답이 없는 앱: $DOWN"
  else
    bad "등록된 앱이 없습니다"
    note ".env 의 SEED_FILE 경로와 config/apps.seed*.json 을 보세요."
    note "앱보다 백엔드가 먼저 떠서 기능 목록을 못 읽었을 수도 있습니다: docker compose restart backend"
  fi
else
  note "로그인이 안 돼 건너뜁니다."
fi

# ── 6. 공식 앱 포트 ─────────────────────────────────────────────────
head_ "6. 공식 앱 포트"
BAD_PORTS=""
for p in 9101 9102 9103 9111 9112 9113 9114 9115 9116 9117 9118 9119; do
  C=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 8 "$HOST:$p/mcp" 2>/dev/null)
  # MCP 는 그냥 GET 하면 400/405/406 을 돌려줍니다. 그래도 "살아 있다"는 뜻입니다.
  case "$C" in 000|"") BAD_PORTS="$BAD_PORTS $p" ;; esac
done
[ -z "$BAD_PORTS" ] && ok "공식 앱 12개 포트가 모두 응답합니다" \
  || bad "응답 없는 포트:$BAD_PORTS  (docker compose logs --tail=30 <해당 앱>)"

# ── 마무리 ──────────────────────────────────────────────────────────
printf '\n────────────────────────────────────────\n'
printf '  통과 %d · 안됨 %d\n' "$PASS" "$FAIL"
if [ "$FAIL" -gt 0 ]; then
  if [ "$LOCAL_MODE" = 1 ]; then
    printf '  기록 보기:  .local-run/logs/  (안 뜬 것의 이름 .log 를 여세요)\n\n'
  else
    printf '  전체 로그 한 번에 보기:  docker compose logs --tail=80\n\n'
  fi
  exit 1
fi
printf '  다 떴습니다. 브라우저로 %s 접속해서 로그인해 보세요.\n\n' "$WEB"
