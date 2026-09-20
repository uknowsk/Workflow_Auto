#!/bin/sh
# 매일 정해진 시각에 backup.sh 를 부르는 작은 일꾼. backup 컨테이너가 이걸 돌립니다.
# 시각은 .env 의 BACKUP_HOUR (기본 3 = 새벽 3시), 시간대는 TZ.
#
# 1분마다 시계를 보고 "그 시각이고 오늘 아직 안 떴으면" 뜹니다.
# (남은 시간을 계산해 그만큼 자는 방식은 alpine 의 date 가 %-H 를 몰라서 쓰지 않습니다.)
set -eu

TARGET=$(printf '%02d' "${BACKUP_HOUR:-3}")
HERE=$(dirname "$0")
LAST_DONE=""

echo "[backup] 매일 ${TARGET}시에 백업합니다 (지금 $(date '+%Y-%m-%d %H:%M %Z'))"

while true; do
    TODAY=$(date +%Y-%m-%d)
    NOW_HOUR=$(date +%H)

    if [ "$NOW_HOUR" = "$TARGET" ] && [ "$LAST_DONE" != "$TODAY" ]; then
        LAST_DONE="$TODAY"
        # 백업이 한 번 실패해도 일꾼은 살아 있어야 내일 또 뜹니다.
        "$HERE/backup.sh" || echo "[backup] 실패했습니다. 위 메시지를 확인하세요."
    fi

    sleep 60
done
