# 집에서 만들고 회사에서 이어가기

집(이 GitHub 저장소)에서 만든 것을 회사로 가져가서 이어 개발합니다.
**회사 코드는 집으로 돌아올 수 없으므로**, 회사에서 덧붙이는 것이
공통 코어를 건드리지 않도록 처음부터 갈라 두었습니다.

## 무엇이 어디에 있나

| | 내용 | 집 저장소에 올리나 |
|---|---|---|
| **공통 코어** | `backend/`, `frontend/`, `templates/`, `docker-compose.yml` | ✅ 올립니다 |
| **환경 설정** | `.env` (프로필에서 복사해 만든 파일) | ❌ `.gitignore` 처리됨 |
| **회사 앱 목록** | `config/apps.seed.json` | ❌ `.gitignore` 처리됨 |
| **프로필 견본** | `config/profiles/*.env.example` | ✅ 값은 비워서 올립니다 |

**원칙: 회사에서만 아는 값은 전부 환경변수와 `config/` 파일로 뺍니다.
코드는 집과 회사가 같아야 합니다.**

그래서 회사에서 할 일은 보통 이 둘뿐입니다.
1. `.env` 값 채우기
2. `config/apps.seed.json` 에 사내 앱 목록 적기

## 회사에서 처음 세팅하기

```bash
# 1) 집에서 만든 코드를 가져옵니다 (사내 Git 또는 승인된 반입 절차)
# 2) 회사용 설정 파일을 만듭니다
cp config/profiles/company.env.example .env

# 3) .env 를 열어 값을 채웁니다 (아래 표 참고)
# 4) 사내 앱 목록 파일을 만듭니다
cp config/apps.seed.example.json config/apps.seed.json

# 5) 실행
docker compose up -d --build
```

## .env 에서 회사가 채워야 할 값

| 값 | 설명 |
|---|---|
| `APP_ENV` | `production` 으로 두세요. 위험한 설정이 남아 있으면 서버가 아예 뜨지 않습니다 |
| `CORS_ORIGINS` | 사용자가 접속할 화면 주소. 쉼표로 여러 개. 운영에서 `*` 는 쓸 수 없습니다 |
| `SECRET_KEY` | 로그인 출입증 서명값. 긴 임의 문자열로 반드시 바꾸세요 |
| `ENCRYPTION_KEY` | 앱 접속 정보를 DB 에 잠가 넣을 열쇠. 비우면 `SECRET_KEY` 를 같이 씁니다 |
| `LLM_BASE_URL` | Gauss 의 OpenAI 호환 주소. 보통 `.../v1` 로 끝납니다 |
| `LLM_API_KEY` | 발급받은 키 |
| `LLM_MODEL` | 사내에서 알려준 모델 이름 |
| `LLM_TOOL_MODE` | Gauss 가 tool calling 을 지원하면 `native`, 아니면 `json` |
| `ADMIN_USER_IDS` | 관리자 사번. 쉼표로 여러 명. 이 사람만 앱을 공식 승인할 수 있습니다 |
| `POSTGRES_PASSWORD` / `DATABASE_URL` | 사내에서 정한 DB 비밀번호 |
| `NEXT_PUBLIC_API_BASE` | 사내 사용자가 접속할 백엔드 주소 |
| `PIP_INDEX_URL` / `NPM_REGISTRY` | 사내 패키지 미러(Nexus 등). 폐쇄망이면 필요합니다 |

## 코어를 건드리지 않고 바꿀 수 있는 것들

| 바꾸고 싶은 것 | 손댈 곳 | 코어 수정 |
|---|---|---|
| LLM 을 Gauss 로 | `.env` 의 `LLM_*` | 없음 |
| Gauss 가 함수 호출을 못 할 때 | `.env` 의 `LLM_TOOL_MODE=json` | 없음 |
| 사내 앱 목록 | `config/apps.seed.json` | 없음 |
| 관리자 지정 | `.env` 의 `ADMIN_USER_IDS` | 없음 |
| 사내 SSO 로그인 연결 | `backend/app/deps.py` 한 파일 | 이 파일만 |
| 사내 패키지 미러 | `.env` 의 `PIP_INDEX_URL` | 없음 |

`backend/app/deps.py` 는 일부러 짧게 만들어 두었습니다. 지금은 `X-User-Id`
헤더에서 사번을 읽지만, 사내에 붙일 때는 이 파일 하나만 사내 SSO 방식으로
바꾸면 나머지 코드는 손댈 필요가 없습니다.

## 폐쇄망 확인 사항

외부 인터넷이 필요한 것은 하나도 없습니다.

- FastAPI, PostgreSQL, Redis, React, Docker, MCP 전부 오픈소스이고 사내 설치 가능
- MCP 는 서비스가 아니라 통신 규격이라 외부 연결이 없습니다
- LLM 은 사내 Gauss 를 씁니다
- 다만 **처음 설치할 때** 파이썬/노드 라이브러리를 받아야 하므로
  사내 패키지 미러(Nexus 등)가 필요합니다. `.env` 에 주소를 넣으면 됩니다
- Docker 이미지도 사내 레지스트리 미러가 필요할 수 있습니다.
  각 `Dockerfile` 의 `FROM` 줄을 사내 주소로 바꾸세요

## 집에서 개발할 때

```bash
cp config/profiles/home.env.example .env
docker compose up -d --build
```

집에서는 LLM 이 없어도 구조는 다 돌아갑니다. LLM 을 붙여 보고 싶으면
Ollama 같은 걸 켜 두고 `.env` 의 `LLM_BASE_URL` 을 거기로 맞추면 됩니다.
Gauss 도 OpenAI 호환이므로, 집에서 OpenAI 호환 엔드포인트로 테스트해 두면
회사에서는 주소만 바꿔 끼우면 그대로 돕니다.


## 처음 띄울 때 걸리면 (일부러 막은 것입니다)

`APP_ENV=production` 이면 서버가 뜨기 전에 위험한 설정을 점검합니다. 이런 메시지가
나오면 **버그가 아니라 일부러 막은 것**입니다. 적힌 대로 `.env` 를 고치고 다시 띄우세요.

```
[서버를 띄우지 않았습니다] APP_ENV=production 인데 위험한 설정이 3개 남아 있습니다.
  1. DEV_HEADER_AUTH=true 입니다. ...
  2. SECRET_KEY 가 예시값 그대로입니다. ...
  3. CORS_ORIGINS 가 * 입니다. ...
```

경고만 찍으면 아무도 안 보고 그대로 운영에 올라가기 때문에 아예 안 뜨게 했습니다.
개발 PC 는 `APP_ENV` 를 지우거나 `dev` 로 두면 지금까지처럼 편하게 쓸 수 있습니다.

## 앱 접속 정보는 잠겨서 저장됩니다

앱을 등록할 때 넣는 토큰·비밀번호(`auth_headers`)는 `ENCRYPTION_KEY` 로 잠가서
DB 에 넣습니다. DB 를 내려받아도 그대로 보이지 않습니다.

- 이 기능을 올리기 **전에** 등록해 둔 앱은 아직 안 잠겨 있습니다. 한 번 정리하세요.
  ```bash
  docker compose exec backend python /srv/scripts/seal_secrets.py          # 무엇이 바뀔지만 보기
  docker compose exec backend python /srv/scripts/seal_secrets.py --apply  # 실제로 잠그기
  ```
- **`ENCRYPTION_KEY` 를 바꾸면 이미 저장된 접속 정보는 못 풉니다.** 앱 등록 화면에서
  다시 넣어야 합니다. `SECRET_KEY` 와 따로 둔 이유가 이것입니다 — 로그인 열쇠만
  바꾸고 싶을 때 앱 접속 정보를 건드리지 않아도 됩니다.

## 백업

`docker compose up -d` 를 하면 백업도 같이 돕니다(매일 새벽 3시, 14일치).
자세한 것은 [docs/BACKUP.md](BACKUP.md) 를 보세요. **`.env` 는 백업에 들어가지 않으니
따로 한 번 안전한 곳에 보관하세요.**
