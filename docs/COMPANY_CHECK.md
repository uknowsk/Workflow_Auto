# 회사 PC 에서 한 번 띄워 보기 (확인용)

**목적: 옮기는 게 아니라 "회사 PC 와 사내망에서 제대로 뜨는지, 뭐가 막히는지" 보는 것.**
개발은 계속 집에서 하고, 여기서는 확인만 합니다.
실제로 사람들에게 열어 주는 절차는 [DEPLOY_COMPANY.md](DEPLOY_COMPANY.md) 에 있습니다.

전부 네 걸음입니다: **가져오기 → 점검 → 띄우기 → 확인.**

---

## 0. 두 가지 길 — 먼저 여기서 고르세요

| | 도커로 띄우기 | **도커 없이 띄우기** |
|---|---|---|
| 필요한 것 | Docker Desktop | Python 3.11+, Node 20+ |
| 데이터베이스 | PostgreSQL | SQLite 파일 하나 |
| 띄우는 명령 | `docker compose up -d --build` | `scripts\run_local.ps1` |
| "계획 세우기" | 됨 (Gauss 주소가 있으면) | 안 됨 (Redis 필요) |
| 나머지 화면 | 다 됨 | 다 됨 |

**Docker Desktop 은 WSL2 나 Hyper-V 위에서만 돕니다.** 사내 정책으로 그 둘이 막혀 있으면
설치해도 못 씁니다. 사내 보안망에서는 흔한 일입니다. 그때는 오른쪽 길로 가면 됩니다.
Python 과 Node 만 있으면 되고, 관리자 권한도 필요 없습니다.

어느 쪽인지 모르겠으면 그냥 점검 스크립트를 돌리세요. 도커가 없으면 알아서
"도커 없이 띄우세요" 라고 알려 주고, `[막힘]` 으로 세지도 않습니다.

### 준비물

| 무엇 | 왜 필요한가 | 없으면 |
|---|---|---|
| **Git** | 코드를 가져옵니다 | 사내 소프트웨어 센터에서 설치 (또는 ZIP 으로 받아도 됩니다) |
| **Python 3.11+ / Node 20+** | 도커 없이 띄울 때 씁니다 | 사내 소프트웨어 센터. 설치할 때 "Add to PATH" 를 켜세요 |
| **Docker Desktop** (쓸 수 있으면) | 서버·DB·앱 15개를 한 번에 띄웁니다 | WSL2/Hyper-V 가 막혀 있으면 포기하고 도커 없이 가세요 |
| **사내 PyPI 미러 주소** | 폐쇄망에서 파이썬 라이브러리를 받습니다 | 설치가 중간에 멈춥니다. IT 에 Nexus/Artifactory 주소를 물어보세요 |
| **사내 npm 미러 주소** | 화면(frontend) 빌드에 씁니다 | 화면 빌드가 멈춥니다 |

Docker Desktop 을 쓸 수 있다면 **켜 두어야** 합니다. 꺼져 있으면 `npipe ...` 오류가 납니다.

---

## 1. 가져오기

```
git clone https://github.com/uknowsk/Workflow_Auto.git
cd Workflow_Auto
```

사내망에서 GitHub 이 막혀 있으면, 집에서 ZIP 으로 내려받아 승인된 반입 절차로 옮깁니다.

---

## 2. 점검 — 필요한 게 다 있는지 먼저 봅니다

**Windows**

```
powershell -ExecutionPolicy Bypass -File scripts\check_ready.ps1 -Fix -Simple
```

**맥 / 리눅스**

```
bash scripts/check_ready.sh --fix --simple
```

이 한 줄이 여덟 가지를 봅니다.

1. git / docker / docker compose 가 있는지
2. **Docker Desktop 이 켜져 있는지**
3. 디스크 여유 (15GB 쯤 필요합니다)
4. `.env` 가 있는지 — `--simple` 을 붙이면 **확인용 설정을 알아서 만들어 줍니다**
5. 위험한 설정이 남아 있는지 (운영으로 올릴 때만 막힘으로 봅니다)
6. **사내 PyPI 미러에 필요한 패키지가 실제로 있는지** — `requirements.txt` 를 읽어 이름과 버전까지 하나씩 확인합니다. 특히 `cryptography` 는 최근에 새로 들어온 것이라 미러에 없을 수 있습니다
7. npm 미러에 닿는지
8. 쓸 포트 13개가 비어 있는지

결과는 `[ OK ] / [주의] / [막힘]` 세 가지로만 나옵니다. **[막힘] 을 먼저 해결하세요.**
그대로 두면 `docker compose up` 이 중간에 멈춥니다.

### 자동 설치

```
powershell -ExecutionPolicy Bypass -File scripts\check_ready.ps1 -Install
```

없는 프로그램을 `winget` 으로 설치해 봅니다.
사내망에서 winget 이 막혀 있으면 "사내 소프트웨어 센터를 쓰세요" 라고 알려 줍니다.
**Docker Desktop 설치는 관리자 권한을 물어보므로, 자동으로 끝까지 되지 않을 수 있습니다.**
그럴 때는 손으로 설치하고 위 점검을 다시 돌려 제대로 깔렸는지만 확인하면 됩니다.

### 미러를 실제로 두드려 보기 (느립니다)

```
powershell -ExecutionPolicy Bypass -File scripts\check_ready.ps1 -Deep
bash scripts/check_ready.sh --deep
```

도커 기본 이미지 4개를 실제로 받아 보고, 사내 미러에서 `cryptography` 를 진짜로
내려받아 봅니다. "목록에는 있는데 실제로는 안 받아지는" 경우까지 걸러 줍니다.

---

## 3. 띄우기

### 도커가 있으면

```
docker compose up -d --build
```

처음에는 이미지를 받고 빌드하느라 **10~20분** 걸립니다. 두 번째부터는 1분 안쪽입니다.

### 도커가 없으면 (WSL2 가 막힌 회사 PC)

```
powershell -ExecutionPolicy Bypass -File scripts\run_local.ps1
```

맥·리눅스면 `bash scripts/run_local.sh` 입니다. 처음 한 번은 꾸러미를 받느라
**3~10분** 걸리고, 두 번째부터는 1분 안쪽입니다. 이 스크립트가 하는 일은 이렇습니다.

1. Python 3.11+ 과 Node 20+ 가 있는지 보고, 없으면 거기서 멈춥니다
2. `.venv-local\` 에 파이썬 전용 방을 만들고 꾸러미를 받습니다 (`.env` 의 사내 미러 주소를 씁니다)
3. 앱 목록의 주소를 도커용 이름(`app-mail:9101`)에서 `127.0.0.1:9101` 로 바꿔 사본을 만듭니다
4. 공식 앱 11개를 띄우고, **다 뜬 뒤에** 백엔드를 띄웁니다 (순서가 바뀌면 앱스토어가 빕니다)
5. 화면을 띄웁니다
6. 로그인 정보와 주소를 찍어 줍니다

내릴 때는 `scripts\stop_local.ps1` (맥·리눅스는 `bash scripts/stop_local.sh`).
데이터와 기록은 `.local-run\` 에 남습니다. 통째로 지우려면 그 폴더만 지우면 됩니다.

**도커 없이 띄우면 "계획 세우기"만 안 됩니다.** 그 기능은 Redis 가 있어야 요청이
접수되는데, 어차피 Gauss(사내 LLM) 주소가 없으면 도커로 띄워도 안 되는 기능입니다.
로그인·앱스토어·대시보드·도구·공식 앱 11개·양식 채우기는 전부 그대로 됩니다.

---

## 4. 확인 — 제대로 떴는지 봅니다

**Windows**

```
powershell -ExecutionPolicy Bypass -File scripts\check_running.ps1
```

**맥 / 리눅스**

```
bash scripts/check_running.sh
```

여섯 가지를 봅니다.

1. 컨테이너가 전부 `running` 인지 (아니면 어느 것이 죽었는지 이름을 찍어 줍니다)
2. 백엔드 `/health` — DB·Redis 가 붙었는지, LLM 주소가 뭐로 잡혀 있는지
3. 화면(3000번)이 열리는지
4. `.env` 의 관리자 계정으로 **실제로 로그인이 되는지**
5. 앱스토어에 앱이 몇 개 올라왔는지, **응답 안 하는 앱이 있는지**
6. 공식 앱 11개 포트가 살아 있는지

다른 PC 에서 접속해 보려면 주소를 넘깁니다.

```
powershell -ExecutionPolicy Bypass -File scripts\check_running.ps1 -HostUrl http://서버주소
bash scripts/check_running.sh --host http://서버주소
```

---

## 자주 걸리는 것

| 증상 | 원인 | 할 일 |
|---|---|---|
| `npipe ...` 오류 | Docker Desktop 이 꺼져 있음 | 켜고 고래 아이콘이 Running 이 된 뒤 다시 |
| Docker Desktop 이 아예 안 깔림/안 켜짐 | WSL2·Hyper-V 가 사내 정책으로 막힘 | 도커를 포기하고 `scripts\run_local.ps1` 로 띄우세요 |
| `run_local` 이 Python 이 없다고 함 | PATH 에 없거나 3.10 이하 | 설치할 때 "Add Python to PATH" 를 켜고, PowerShell 창을 새로 여세요 |
| `run_local` 이 꾸러미를 못 받음 | 사내 미러 주소 미설정 | `.env` 에 `PIP_INDEX_URL` / `NPM_REGISTRY` 를 넣고 다시 실행 |
| 빌드가 `pip install` 에서 멈춤 | 사내 PyPI 미러 미설정 또는 패키지 없음 | `.env` 에 `PIP_INDEX_URL`, `PIP_TRUSTED_HOST`. 그래도 안 되면 IT 에 **cryptography 44.0.0** 요청 |
| `docker pull` 이 안 됨 | 사내 도커 레지스트리 미러 필요 | 각 `Dockerfile` 의 `FROM` 줄을 사내 주소로 바꾸거나 도커 설정에 미러 등록 |
| 서버가 뜨자마자 죽고 "위험한 설정" 메시지 | `APP_ENV=production` 인데 값이 예시 그대로 | 일부러 막은 것입니다. 적힌 대로 `.env` 를 고치세요 |
| 로그인이 안 됨 | 계정은 **처음 기동할 때** 만들어집니다 | `.env` 에 `ADMIN_RESET_PASSWORD=true` 두고 `docker compose restart backend` |
| 앱스토어가 비어 있음 | 앱보다 백엔드가 먼저 떠서 기능 목록을 못 읽음 | `docker compose restart backend` |
| 화면은 뜨는데 "계획 세우기"만 실패 | Gauss 주소가 없음 | `.env` 의 `LLM_*` 를 채우면 됩니다. 나머지 화면은 LLM 없이 다 돕니다 |

---

## 확인이 끝나고, 진짜로 쓸 때

확인용 `.env` 는 개발용 통로(`DEV_HEADER_AUTH=true`)가 열려 있어 **그대로 사람들에게
열어 주면 안 됩니다.** 운영으로 넘어가는 절차는 [DEPLOY_COMPANY.md](DEPLOY_COMPANY.md)
에 있고, 거기서도 같은 점검 스크립트를 쓰면 됩니다.

```
copy config\profiles\company.env.example .env      # 회사 프로필로 다시 만들고 값 채우기
powershell -ExecutionPolicy Bypass -File scripts\check_ready.ps1
```

이때는 `APP_ENV=production` 이라 예시값이 하나라도 남아 있으면 `[막힘]` 으로 잡힙니다.
