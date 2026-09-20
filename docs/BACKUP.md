# 백업과 되살리기

서버가 죽거나, 누가 실수로 지우거나, 디스크가 고장 났을 때 돌아갈 자리를 만들어 둡니다.

## 무엇을 백업하나

| | 들어 있는 것 | 백업에 포함 |
|---|---|---|
| **DB** | 계정, 앱 목록, 카드, 실행 이력, 메모·그림, 감사 기록, 부서, 의견 | ✅ |
| **파일 폴더** | 올린 앱 패키지, 양식 파일, 공식 앱들이 쌓아 둔 자료 | ✅ |
| **`.env`** | 비밀번호와 열쇠 | ❌ **일부러 뺐습니다** |

> **`.env` 는 따로 한 번 안전한 곳에 보관하세요.**
> 백업 파일이 있어도 `.env` 가 없으면 서버가 뜨지 않고,
> `ENCRYPTION_KEY` 가 없으면 앱 접속 정보를 풀 수 없습니다.

## 언제 뜨나

`docker compose up -d` 를 하면 `backup` 컨테이너가 같이 떠서
**매일 새벽 3시**에 한 벌 뜹니다. **14일**치만 남기고 오래된 것은 지웁니다.

`.env` 에서 바꿀 수 있습니다.

| 값 | 기본 | 설명 |
|---|---|---|
| `BACKUP_HOUR` | `3` | 몇 시에 뜰지 (0~23) |
| `BACKUP_KEEP_DAYS` | `14` | 며칠치를 남길지 |
| `BACKUP_HOST_DIR` | `./backups` | 백업 파일을 둘 서버 폴더 |
| `BACKUP_SECONDARY_HOST_DIR` | (없음) | 회사 공유 폴더 경로 |
| `BACKUP_SECONDARY_DIR` | (비어 있음) | `/srv/secondary` 로 적으면 공유 폴더에도 복사 |
| `TZ` | `Asia/Seoul` | "새벽 3시"가 어느 나라 3시인지 |

### 회사 공유 폴더에도 한 벌 더 두기 (권장)

서버 디스크가 통째로 죽으면 서버 안 백업도 같이 죽습니다. `.env` 에 두 줄을 넣으세요.

```
BACKUP_SECONDARY_HOST_DIR=/mnt/사내공유폴더/workflow-backups
BACKUP_SECONDARY_DIR=/srv/secondary
```

## 손으로 지금 한 번 뜨기

```bash
docker compose run --rm backup /srv/scripts/backup.sh
```

만들어지는 것 (`backups/2026-09-20_0300/`)

```
db.dump        DB 통째로
files.tar.gz   파일 폴더 통째로
INFO.txt       언제 뜬 것인지, 크기, 되살리는 명령
```

## 되살리기

되살리면 **지금 DB 의 내용은 지워지고** 그 시점으로 바뀝니다. 그래서 세 단계입니다.

```bash
# 1) 쓰는 사람이 없게 잠깐 멈춥니다
docker compose stop backend worker

# 2) 어떤 백업이 있는지 보고
docker compose run --rm restore /srv/scripts/restore.sh

# 3) 고른 시점으로 되살립니다 (--yes 가 없으면 아무것도 안 합니다)
docker compose run --rm restore /srv/scripts/restore.sh 2026-09-20_0300 --yes

# 4) 다시 띄웁니다
docker compose start backend worker
```

## 1년에 한 번은 연습하세요

**되살려 본 적 없는 백업은 백업이 아닙니다.** 진짜 사고가 났을 때 처음 해 보면
그때 뭔가 빠져 있다는 걸 알게 됩니다.

이 백업·되살리기는 2026-09-20 에 진짜 PostgreSQL 에 자료를 넣고,
표를 지우고 파일도 지운 뒤, 위 순서대로 되살려서 **계정·앱·잠긴 접속 정보·파일이
전부 돌아오는 것까지 확인**했습니다.
