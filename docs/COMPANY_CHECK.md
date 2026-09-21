# 회사 PC 에서 한 번 띄워 보기 (확인용)

**목적: 옮기는 게 아니라 "회사 PC 와 사내망에서 제대로 뜨는지, 뭐가 막히는지" 보는 것.**
개발은 계속 집에서 하고, 여기서는 확인만 합니다.
실제로 사람들에게 열어 주는 절차는 [DEPLOY_COMPANY.md](DEPLOY_COMPANY.md) 에 있습니다.

전부 네 걸음입니다: **가져오기 → 점검 → 띄우기 → 확인.**

---

## 0. 준비물

| 무엇 | 왜 필요한가 | 없으면 |
|---|---|---|
| **Git** | 코드를 가져옵니다 | 사내 소프트웨어 센터에서 설치 (또는 ZIP 으로 받아도 됩니다) |
| **Docker Desktop** | 서버·DB·앱 15개를 한 번에 띄웁니다 | 사내 소프트웨어 센터. **설치에 관리자 권한이 필요해 자동 설치가 안 될 수 있습니다** |
| **사내 PyPI 미러 주소** | 폐쇄망에서 파이썬 라이브러리를 받습니다 | 설치가 중간에 멈춥니다. IT 에 Nexus/Artifactory 주소를 물어보세요 |
| **사내 npm 미러 주소** | 화면(frontend) 빌드에 씁니다 | 화면 빌드가 멈춥니다 |

Docker Desktop 은 **켜 두어야** 합니다. 꺼져 있으면 `npipe ...` 오류가 납니다.
이게 가장 자주 걸리는 것이라 점검 스크립트가 제일 먼저 봅니다.

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

```
docker compose up -d --build
```

처음에는 이미지를 받고 빌드하느라 **10~20분** 걸립니다. 두 번째부터는 1분 안쪽입니다.

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
6. 공식 앱 10개 포트가 살아 있는지

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
