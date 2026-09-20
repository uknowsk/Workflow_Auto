#!/bin/sh
# 백업에서 되살리기.
#
#   어떤 백업이 있는지 보기:
#     docker compose run --rm restore /srv/scripts/restore.sh
#   되살리기 (지금 DB 를 지우고 그 시점으로 바꿉니다):
#     docker compose run --rm restore /srv/scripts/restore.sh 2026-09-20_0300 --yes
#
# 되살리기 전에 backend·worker 를 멈춰 두세요:
#     docker compose stop backend worker
set -eu

BACKUP_DIR="${BACKUP_DIR:-/srv/backups}"
BACKUP_SOURCES="${BACKUP_SOURCES:-/srv/sources}"
STAMP="${1:-}"

if [ -z "$STAMP" ] || [ "$STAMP" = "--help" ]; then
    echo "가지고 있는 백업:"
    ls -1 "$BACKUP_DIR" 2>/dev/null | grep '^20' | sed 's/^/  /' || echo "  (없습니다)"
    echo ""
    echo "사용법: restore.sh <날짜_시각> --yes     예) restore.sh 2026-09-20_0300 --yes"
    exit 0
fi

SRC="$BACKUP_DIR/$STAMP"
[ -d "$SRC" ] || { echo "그런 백업이 없습니다: $SRC"; exit 1; }
[ -f "$SRC/db.dump" ] || { echo "$SRC 안에 db.dump 가 없습니다"; exit 1; }

echo "되살릴 백업: $SRC"
cat "$SRC/INFO.txt" 2>/dev/null | sed 's/^/  /' || true
echo ""

case "${2:-}" in
    --yes) ;;
    *)
        echo "지금 DB 의 내용은 지워지고 위 시점으로 바뀝니다."
        echo "정말 하려면 --yes 를 붙여 다시 실행하세요."
        exit 0
        ;;
esac

DB_URL=$(printf '%s' "${DATABASE_URL:?DATABASE_URL 이 없습니다}" | sed 's|+psycopg||; s|+asyncpg||')

# --clean --if-exists: 같은 이름의 표가 이미 있어도 지우고 새로 넣습니다.
pg_restore --dbname="$DB_URL" --clean --if-exists --no-owner "$SRC/db.dump"
echo "[restore] DB 완료"

if [ -f "$SRC/files.tar.gz" ]; then
    if [ -d "$BACKUP_SOURCES" ]; then
        tar xzf "$SRC/files.tar.gz" -C "$BACKUP_SOURCES"
        echo "[restore] 파일 완료"
    else
        echo "[restore] $BACKUP_SOURCES 가 없어 파일은 건너뜁니다"
    fi
fi

echo "[restore] 끝. 이제 docker compose start backend worker 로 다시 띄우세요."
