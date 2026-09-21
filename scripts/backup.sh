#!/bin/sh
# 백업 한 번 뜨기. 매일 새벽에 backup_daily.sh 가 이걸 부릅니다.
#
#   손으로 지금 한 번 뜨기:
#     docker compose run --rm backup /srv/scripts/backup.sh
#
# 만들어지는 것 (BACKUP_DIR/2026-09-20_0300/)
#   db.dump        DB 통째로 (pg_dump -Fc)
#   files.tar.gz   앱 패키지·양식·공식 앱들이 쌓아 둔 파일
#   INFO.txt       언제 뜬 것인지, 크기가 얼마인지
#
# .env 는 일부러 백업에 넣지 않습니다(비밀번호가 들어 있어서).
# 따로 안전한 곳에 한 번 보관해 두세요. 없으면 복구해도 서버가 못 뜹니다.
set -eu

BACKUP_DIR="${BACKUP_DIR:-/srv/backups}"
BACKUP_KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
BACKUP_SOURCES="${BACKUP_SOURCES:-/srv/sources}"
BACKUP_SECONDARY_DIR="${BACKUP_SECONDARY_DIR:-}"

# DATABASE_URL 은 앱이 쓰는 모양(postgresql+psycopg://...)이라 pg_dump 가 모릅니다.
# +psycopg 만 떼어 내면 그대로 쓸 수 있습니다.
DB_URL=$(printf '%s' "${DATABASE_URL:?DATABASE_URL 이 없습니다}" | sed 's|+psycopg||; s|+asyncpg||')

STAMP=$(date +%Y-%m-%d_%H%M)
OUT="$BACKUP_DIR/$STAMP"
mkdir -p "$OUT"

echo "[backup] $STAMP 시작"

# 1) DB
pg_dump --dbname="$DB_URL" --format=custom --file="$OUT/db.dump"
echo "[backup] DB 완료"

# 2) 파일 (읽기 전용으로 붙여 둔 데이터 폴더들)
if [ -d "$BACKUP_SOURCES" ]; then
    tar czf "$OUT/files.tar.gz" -C "$BACKUP_SOURCES" .
    echo "[backup] 파일 완료"
else
    echo "[backup] $BACKUP_SOURCES 가 없어 파일은 건너뜁니다"
fi

# 3) 뭐가 들었는지 적어 두기 (복구할 때 사람이 먼저 읽는 파일)
{
    echo "뜬 시각      : $(date '+%Y-%m-%d %H:%M:%S %Z')"
    echo "DB           : $(printf '%s' "$DB_URL" | sed 's|://[^@]*@|://***@|')"
    echo "크기         :"
    du -h "$OUT"/* 2>/dev/null | sed 's/^/  /'
    echo ""
    echo "되살리는 법  : scripts/restore.sh $STAMP --yes"
    echo "주의         : .env 는 여기 없습니다. 따로 보관한 것을 같이 쓰세요."
} > "$OUT/INFO.txt"

# 4) 오래된 것 지우기 (디스크가 꽉 차서 서버가 멈추는 게 흔한 사고입니다)
find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -name '20*' -mtime "+$BACKUP_KEEP_DAYS" \
    -exec rm -rf {} + 2>/dev/null || true

# 5) 회사 공유 폴더로 한 벌 더 (서버 디스크가 통째로 죽는 경우 대비)
if [ -n "$BACKUP_SECONDARY_DIR" ] && [ "$BACKUP_SECONDARY_DIR" != "$BACKUP_DIR" ]; then
    if [ -d "$BACKUP_SECONDARY_DIR" ] && [ ! -e "$BACKUP_SECONDARY_DIR/$STAMP/db.dump" ]; then
        mkdir -p "$BACKUP_SECONDARY_DIR/$STAMP"
        cp "$OUT"/* "$BACKUP_SECONDARY_DIR/$STAMP/"
        find "$BACKUP_SECONDARY_DIR" -mindepth 1 -maxdepth 1 -type d -name '20*' \
            -mtime "+$BACKUP_KEEP_DAYS" -exec rm -rf {} + 2>/dev/null || true
        echo "[backup] 공유 폴더에도 복사했습니다: $BACKUP_SECONDARY_DIR/$STAMP"
    else
        # 공유 폴더가 안 붙어 있어도 1차 백업은 이미 끝났으므로 실패로 보지 않습니다.
        echo "[backup] 경고: BACKUP_SECONDARY_DIR($BACKUP_SECONDARY_DIR) 가 안 보입니다. 1차 백업만 남았습니다."
    fi
fi

echo "[backup] 끝: $OUT"
