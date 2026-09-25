#!/usr/bin/env bash
# 회사 PC에서 Workflow Auto 를 띄우기 "전에" 필요한 것이 다 있는지 점검합니다.
#
#   bash scripts/check_ready.sh          # 점검만
#   bash scripts/check_ready.sh --fix    # .env 가 없으면 회사 프로필에서 만들어 줍니다
#   bash scripts/check_ready.sh --fix --simple  # "그냥 떠는지만 보는" 확인용 .env 로 만듭니다
#   bash scripts/check_ready.sh --deep   # 사내 미러에서 실제로 패키지를 받아 봅니다(느림)
#
# 맥/리눅스용입니다. 회사 PC 가 Windows 면 scripts/check_ready.ps1 을 쓰세요.
set -u

cd "$(dirname "$0")/.." || exit 1

FIX=0; DEEP=0; HOME_PROFILE=0
for a in "$@"; do
  case "$a" in
    --fix) FIX=1 ;;
    --deep) DEEP=1 ;;
    --simple|--home) HOME_PROFILE=1 ;;
    *) echo "모르는 옵션: $a"; exit 2 ;;
  esac
done

PASS=0; WARN=0; FAIL=0
DEV_MODE=0
ok()   { printf '  [ OK ] %s\n' "$*"; PASS=$((PASS+1)); }
warn() { printf '  [주의] %s\n' "$*"; WARN=$((WARN+1)); }
bad()  {
  # 확인용(APP_ENV=dev)일 때는 운영 전용 점검을 '주의' 로만 알립니다.
  if [ "$DEV_MODE" = 1 ] && [ "${1:-}" = "--prod-only" ]; then shift; warn "$*"; return; fi
  case "${1:-}" in --prod-only) shift ;; esac
  printf '  [막힘] %s\n' "$*"; FAIL=$((FAIL+1));
}
note() { printf '         %s\n' "$*"; }
head_() { printf '\n== %s ==\n' "$*"; }

# ── 1. 필요한 프로그램 ───────────────────────────────────────────────
head_ "1. 필요한 프로그램"

if command -v git >/dev/null 2>&1; then ok "git $(git --version | awk '{print $3}')"
else bad "git 이 없습니다"; note "사내 소프트웨어 센터에서 Git 을 설치하세요."; fi

HAVE_DOCKER=0
if command -v docker >/dev/null 2>&1; then
  HAVE_DOCKER=1
  ok "docker $(docker --version | awk '{print $3}' | tr -d ,)"
else
  warn "docker 가 없습니다"
  note "Docker Desktop 은 WSL2 나 Hyper-V 가 있어야 돕니다. 사내 정책으로 그게 막혀 있으면"
  note "설치해도 못 씁니다. 그럴 때는 도커 없이 띄우세요:  bash scripts/run_local.sh"
  note "(Python 3.11+ 와 Node 20+ 만 있으면 됩니다. 바로 아래에서 확인합니다)"
fi

if [ "$HAVE_DOCKER" = 1 ]; then
  if docker compose version >/dev/null 2>&1; then ok "docker compose $(docker compose version --short 2>/dev/null)"
  else bad "docker compose(v2) 가 없습니다"; note "Docker Desktop 최신판에는 들어 있습니다."; fi

  if docker info >/dev/null 2>&1; then ok "도커가 실행 중입니다"
  else
    bad "도커가 실행되고 있지 않습니다"
    note "Docker Desktop 을 켜고 고래 아이콘이 'Running' 이 된 뒤 다시 실행하세요."
  fi
fi

# 도커가 없으면 이 둘만 있으면 띄울 수 있습니다(scripts/run_local.sh).
PYOK=0
for c in python3.13 python3.12 python3.11 python3 python; do
  command -v "$c" >/dev/null 2>&1 || continue
  v=$("$c" -c 'import sys;print(sys.version_info[0]*100+sys.version_info[1])' 2>/dev/null)
  if [ -n "$v" ] && [ "$v" -ge 311 ]; then PYOK=1; ok "python $("$c" --version 2>&1 | awk '{print $2}')"; break; fi
done
if [ "$PYOK" = 0 ]; then
  [ "$HAVE_DOCKER" = 1 ] && warn "Python 3.11 이상이 없습니다 (도커로 띄우면 없어도 됩니다)" \
                          || bad "Python 3.11 이상이 없습니다 — 도커가 없으니 이건 꼭 필요합니다"
fi

if command -v node >/dev/null 2>&1 && [ "$(node --version | sed 's/^v//' | cut -d. -f1)" -ge 20 ]; then
  ok "node $(node --version)"
elif command -v node >/dev/null 2>&1; then
  warn "node $(node --version) — 20 이상이 필요합니다"
else
  [ "$HAVE_DOCKER" = 1 ] && warn "Node.js 가 없습니다 (도커로 띄우면 없어도 됩니다)" \
                          || bad "Node.js 20 이상이 없습니다 — 도커가 없으니 이건 꼭 필요합니다"
fi

# ── 2. 디스크 여유 ──────────────────────────────────────────────────
head_ "2. 디스크 여유"
AVAIL_GB=$(df -Pk . 2>/dev/null | awk 'NR==2{printf "%d", $4/1024/1024}')
if [ -n "${AVAIL_GB:-}" ] && [ "$AVAIL_GB" -ge 15 ]; then ok "남은 공간 약 ${AVAIL_GB}GB"
elif [ -n "${AVAIL_GB:-}" ]; then warn "남은 공간 약 ${AVAIL_GB}GB (이미지 빌드에 15GB 쯤 권장)"
else warn "남은 공간을 확인하지 못했습니다"; fi

# ── 3. 설정 파일(.env) ──────────────────────────────────────────────
head_ "3. 설정 파일 (.env)"
if [ ! -f .env ]; then
  if [ "$FIX" = 1 ] && [ "$HOME_PROFILE" = 1 ]; then
    cp config/profiles/home.env.example .env
    ok ".env 를 확인용(개발) 프로필로 만들었습니다 — 값을 안 채워도 그냥 뜹니다"
  elif [ "$FIX" = 1 ]; then
    cp config/profiles/company.env.example .env
    ok ".env 를 회사 프로필에서 만들었습니다"
    note "열어서 값을 채운 뒤 이 스크립트를 다시 실행하세요."
  elif [ "$HAVE_DOCKER" = 0 ]; then
    warn ".env 가 없습니다 (도커 없이 띄우는 scripts/run_local.sh 는 없어도 됩니다)"
    note "사내 미러 주소를 넣어야 한다면:  cp config/profiles/company.env.example .env"
  else
    bad ".env 가 없습니다"
    note "cp config/profiles/company.env.example .env   (또는 --fix 옵션)"
  fi
fi

getenv() { [ -f .env ] || return 0; sed -n "s/^$1=//p" .env | tail -1 | tr -d '\r'; }

if [ -f .env ]; then
  APP_ENV=$(getenv APP_ENV)
  if [ "$APP_ENV" = "production" ]; then ok "APP_ENV=production"
  else
    ok "APP_ENV='${APP_ENV:-dev}' — 확인용입니다. 아래 값들은 참고만 하세요"
    note "실제로 사람들에게 열어 줄 때는 APP_ENV=production 으로 바꾸고 다시 점검하세요."
    DEV_MODE=1
  fi

  for pair in "SECRET_KEY:반드시_바꾸세요" "ENCRYPTION_KEY:반드시_바꾸세요_다른값으로"; do
    k=${pair%%:*}; sample=${pair#*:}; v=$(getenv "$k")
    if [ -z "$v" ]; then
      [ "$k" = "ENCRYPTION_KEY" ] && warn "$k 가 비어 있습니다 (SECRET_KEY 를 같이 씁니다)" || bad --prod-only "$k 가 비어 있습니다"
    elif [ "$v" = "$sample" ]; then
      bad --prod-only "$k 가 예시값 그대로입니다 — APP_ENV=production 이면 서버가 뜨지 않습니다"
      note "python3 -c \"import secrets;print(secrets.token_urlsafe(48))\" 로 만들어 넣으세요."
    elif [ "${#v}" -lt 32 ]; then warn "$k 가 짧습니다(${#v}자). 32자 이상을 권합니다"
    else ok "$k 채워져 있습니다"; fi
  done

  CORS=$(getenv CORS_ORIGINS)
  if [ "$CORS" = "*" ]; then bad --prod-only "CORS_ORIGINS=* 입니다 — 운영에서는 서버가 뜨지 않습니다"
  elif [ -z "$CORS" ]; then warn "CORS_ORIGINS 가 비어 있습니다"
  elif [ "$CORS" != "${CORS#*사내서버주소}" ]; then bad --prod-only "CORS_ORIGINS 가 예시 주소 그대로입니다 — 실제 접속 주소로 바꾸세요"
  else ok "CORS_ORIGINS=$CORS"; fi

  DHA=$(getenv DEV_HEADER_AUTH)
  [ "$DHA" = "true" ] && bad --prod-only "DEV_HEADER_AUTH=true 입니다 — 개발용 통로입니다. false 로 두세요" || ok "DEV_HEADER_AUTH=${DHA:-false}"

  ADMPW=$(getenv ADMIN_PASSWORD)
  if [ -z "$ADMPW" ]; then warn "ADMIN_PASSWORD 가 비어 있습니다 — 관리자 계정이 안 만들어집니다"
  elif [ "$ADMPW" = "여기에_비밀번호" ]; then bad --prod-only "ADMIN_PASSWORD 가 예시값 그대로입니다 (로그인 비밀번호가 그 글자 그대로가 됩니다)"
  else ok "ADMIN_ID/ADMIN_PASSWORD 채워져 있습니다"; fi

  APIBASE=$(getenv NEXT_PUBLIC_API_BASE)
  if [ -z "$APIBASE" ]; then warn "NEXT_PUBLIC_API_BASE 가 비어 있습니다 — 화면이 백엔드를 못 찾습니다"
  elif [ "$APIBASE" != "${APIBASE#*사내서버주소}" ]; then bad --prod-only "NEXT_PUBLIC_API_BASE 가 예시 주소 그대로입니다 — 사람들이 접속할 주소로 바꾸세요"
  else ok "NEXT_PUBLIC_API_BASE=$APIBASE"; fi

  LLM=$(getenv LLM_BASE_URL)
  case "$LLM" in
    ""|*사내*) warn "LLM_BASE_URL 이 아직 예시값입니다 — Gauss 주소를 넣기 전까지 '계획 세우기'만 안 됩니다" ;;
    *) ok "LLM_BASE_URL=$LLM" ;;
  esac
fi

# ── 4. 사내 패키지 미러 ─────────────────────────────────────────────
head_ "4. 사내 패키지 미러 (폐쇄망이면 필수)"
PIP_INDEX_URL=$(getenv PIP_INDEX_URL)
if [ -z "$PIP_INDEX_URL" ]; then
  if curl -sSfI --max-time 8 https://pypi.org/simple/ >/dev/null 2>&1; then
    ok "PIP_INDEX_URL 은 비었지만 pypi.org 에 바로 닿습니다"
  else
    bad "PIP_INDEX_URL 이 비어 있고 pypi.org 에도 닿지 않습니다 — 빌드가 여기서 멈춥니다"
    note ".env 에 사내 Nexus/Artifactory 주소를 넣으세요:"
    note "  PIP_INDEX_URL=https://nexus.사내주소/repository/pypi/simple"
    note "  PIP_TRUSTED_HOST=nexus.사내주소"
  fi
else
  ok "PIP_INDEX_URL=$PIP_INDEX_URL"
  # 필요한 패키지가 미러에 실제로 있는지 이름+버전으로 확인합니다.
  #   (특히 cryptography 는 이번에 새로 들어온 것이라 미러에 없을 수 있습니다)
  base="${PIP_INDEX_URL%/}"
  pkgs=$(cat backend/requirements.txt official_apps/requirements.txt 2>/dev/null \
    | sed 's/#.*//' | grep '==' | sed 's/\[.*\]//' | tr -d ' \r')
  miss=0
  for line in $pkgs; do
    name=${line%%==*}; ver=${line##*==}
    norm=$(printf '%s' "$name" | tr 'A-Z_.' 'a-z--')
    body=$(curl -sSL --max-time 15 "$base/$norm/" 2>/dev/null)
    if [ -z "$body" ]; then warn "$name — 미러 응답이 없습니다(확인 필요)"; miss=$((miss+1))
    elif printf '%s' "$body" | grep -qi -- "-$ver"; then :
    else bad "$name==$ver 가 사내 미러에 없습니다"; miss=$((miss+1)); fi
  done
  [ "$miss" = 0 ] && ok "필요한 파이썬 패키지가 사내 미러에 모두 있습니다"
  if [ "$PIP_INDEX_URL" != "${PIP_INDEX_URL#https://}" ] && [ -z "$(getenv PIP_TRUSTED_HOST)" ]; then
    note "사내 인증서 때문에 막히면 PIP_TRUSTED_HOST 도 함께 넣으세요."
  fi
fi

NPM_REGISTRY=$(getenv NPM_REGISTRY)
if [ -n "$NPM_REGISTRY" ]; then ok "NPM_REGISTRY=$NPM_REGISTRY"
elif curl -sSfI --max-time 8 https://registry.npmjs.org/ >/dev/null 2>&1; then ok "npm 공식 저장소에 바로 닿습니다"
else bad "NPM_REGISTRY 가 비어 있고 registry.npmjs.org 에도 닿지 않습니다 — 화면(frontend) 빌드가 멈춥니다"; fi

# ── 5. 도커 이미지 ──────────────────────────────────────────────────
head_ "5. 도커 기본 이미지"
IMAGES="python:3.11-slim node:20-alpine postgres:16-alpine redis:7-alpine"
if [ "$HAVE_DOCKER" = 0 ]; then
  note "도커가 없어 건너뜁니다. scripts/run_local.sh 로 띄우면 이미지는 필요 없습니다."
elif docker info >/dev/null 2>&1; then
  for img in $IMAGES; do
    if docker image inspect "$img" >/dev/null 2>&1; then ok "$img (이미 받아 둠)"
    elif [ "$DEEP" = 1 ]; then
      if docker pull -q "$img" >/dev/null 2>&1; then ok "$img 내려받기 성공"
      else bad "$img 를 받지 못했습니다 — 사내 레지스트리 미러 주소가 필요합니다"
           note "각 Dockerfile 의 FROM 줄을 사내 주소로 바꾸거나, 도커 설정에 미러를 등록하세요."; fi
    else warn "$img 아직 없음 (--deep 을 붙이면 실제로 받아 봅니다)"; fi
  done
else
  warn "도커가 꺼져 있어 이미지 확인을 건너뜁니다"
fi

if [ "$DEEP" = 1 ] && [ -n "$PIP_INDEX_URL" ] && docker info >/dev/null 2>&1; then
  printf '  ... 사내 미러에서 cryptography 를 실제로 받아 보는 중\n'
  if docker run --rm python:3.11-slim pip download --no-deps -d /tmp/x \
       -i "$PIP_INDEX_URL" "cryptography==44.0.0" >/dev/null 2>&1; then
    ok "사내 미러에서 cryptography==44.0.0 내려받기 성공"
  else
    bad "사내 미러에서 cryptography==44.0.0 를 받지 못했습니다"
    note "IT 에 'PyPI 미러에 cryptography 44.0.0 을 올려 달라'고 요청하세요."
  fi
fi

# ── 6. 포트 ─────────────────────────────────────────────────────────
head_ "6. 포트 비어 있나"
PORTS="3000 8000 9001 9101 9102 9103 9111 9112 9113 9114 9115 9116 9117 9118 9119"
busy=""
for p in $PORTS; do
  if (command -v ss >/dev/null 2>&1 && ss -ltn 2>/dev/null | grep -q ":$p ") \
     || (command -v lsof >/dev/null 2>&1 && lsof -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1); then
    busy="$busy $p"
  fi
done
[ -z "$busy" ] && ok "쓰는 포트 13개가 모두 비어 있습니다" || warn "이미 쓰는 중인 포트:$busy (이전에 띄워 둔 것이면 괜찮습니다)"

# ── 마무리 ──────────────────────────────────────────────────────────
printf '\n────────────────────────────────────────\n'
printf '  통과 %d · 주의 %d · 막힘 %d\n' "$PASS" "$WARN" "$FAIL"
if [ "$FAIL" -gt 0 ]; then
  printf '  [막힘] 을 먼저 해결하세요. 그대로 두면 기동 중에 멈춥니다.\n\n'
  exit 1
fi
if [ "$HAVE_DOCKER" = 1 ]; then
  printf '  다음 단계:  docker compose up -d --build\n'
else
  printf '  다음 단계:  bash scripts/run_local.sh      (도커 없이 띄웁니다)\n'
fi
printf '  띄운 뒤   :  bash scripts/check_running.sh\n\n'
