#!/usr/bin/env bash
# scripts/run_local.sh 로 띄운 것들을 내립니다.
set -u
cd "$(dirname "$0")/.." || exit 1
RUN_DIR="$(pwd)/.local-run"

if [ ! -f "$RUN_DIR/pids" ]; then
  echo "내릴 것이 없습니다 (.local-run/pids 가 없습니다)."
  exit 0
fi

n=0
while read -r pid; do
  [ -n "$pid" ] || continue
  if kill "$pid" 2>/dev/null; then n=$((n+1)); fi
done < "$RUN_DIR/pids"

# 화면(next dev)은 자식 프로세스를 하나 더 만듭니다. 포트를 잡고 있으면 같이 내립니다.
sleep 1
for p in 3000 8000 9101 9102 9103 9111 9112 9113 9114 9115 9116 9117 9118 9119; do
  pid=$(command -v lsof >/dev/null 2>&1 && lsof -tiTCP:"$p" -sTCP:LISTEN 2>/dev/null)
  [ -n "$pid" ] && kill $pid 2>/dev/null
done

: > "$RUN_DIR/pids"
echo "$n 개를 내렸습니다. 데이터는 .local-run/ 에 그대로 있습니다."
echo "완전히 지우려면:  rm -rf .local-run"
