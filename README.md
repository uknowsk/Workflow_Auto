# Workflow Auto

자연어로 요청하면, 오케스트레이터가 **등록된 앱들을 알아서 골라 순서대로 부르고**
결과를 합쳐 최종 산출물을 만들어 주는 사내 업무 자동화 앱입니다.

```
"사번 E1001의 이번주 주간보고를 작성해줘"
        ↓
  오케스트레이터가 계획을 세우고
        ↓
  인사조회 앱 호출 → 보고서양식 앱 호출
        ↓
  완성된 주간보고 문서
```

개발자들이 각자 만든 앱은 **고치지 않고** 옆에 얇은 어댑터만 붙여 등록합니다.
등록된 앱은 앱스토어처럼 모아 두고, 사용자는 자주 쓰는 것을 카드로 저장해 씁니다.

> 지금은 **실행되는 최소 뼈대**입니다. 화려한 UI나 완성 기능은 아직 없습니다.

## 5분 만에 띄우기

필요한 것: Docker Desktop (또는 Docker + Compose)

```bash
git clone https://github.com/uknowsk/workflow_auto.git
cd workflow_auto

# 1) 설정 파일 만들기 (집에서 개발할 때)
cp config/profiles/home.env.example .env

# 2) 전부 띄우기
docker compose up -d --build
```

| 주소 | 무엇 |
|---|---|
| http://localhost:3000 | 화면 |
| http://localhost:8000/docs | API 문서 (직접 눌러 볼 수 있습니다) |
| http://localhost:8000/health | 잘 떴는지 확인 |

예시 앱이 자동으로 등록되어 있으므로, 화면에서 바로 요청을 넣어 볼 수 있습니다.

> LLM 을 아직 안 붙였다면 앱 등록·카드·앱스토어까지는 다 되고,
> 실제 요청 실행만 실패합니다. 아래에서 LLM 을 연결하세요.

## Gauss(사내 LLM) 연결하기

`.env` 파일에서 아래 세 줄만 바꾸면 됩니다. 코드는 건드리지 않습니다.

```bash
LLM_BASE_URL=https://사내-gauss-주소/v1    # 보통 /v1 로 끝납니다
LLM_API_KEY=발급받은_키
LLM_MODEL=사내에서_알려준_모델명
```

그리고 Gauss 가 **tool calling(함수 호출)** 을 지원하는지에 따라 한 줄 더:

```bash
LLM_TOOL_MODE=native   # 함수 호출 지원 → 이게 제일 깔끔합니다
LLM_TOOL_MODE=json     # 지원 안 함 → 프롬프트로 JSON 을 받아내는 우회 방식
```

바꾼 뒤 `docker compose up -d` 를 다시 실행하면 적용됩니다.
Gauss 가 OpenAI 호환 형식이라 이것만으로 끝납니다.

## 내 앱 붙이기

**내 앱은 고치지 않습니다.** 옆에 통역사 역할을 하는 작은 파일 하나를 만들어
같이 켜 두면 됩니다.

개발을 몰라도 됩니다 → **[docs/WRAPPER_PROMPT.md](docs/WRAPPER_PROMPT.md)** 의
글상자를 복사해서 Claude / Codex / Cline 에 붙여넣으면 알아서 만들어 줍니다.

- 견본: `templates/mcp_adapter_http/` (웹앱용), `templates/mcp_adapter_cli/` (PC 설치형용)
- 완성 예시: `example_app/` — 기존 앱을 한 줄도 안 고치고 붙인 사례
- 규약 원문: [docs/WRAPPER_SPEC.md](docs/WRAPPER_SPEC.md)

## 앱 등급과 승인

| 등급 | 누가 쓰나 |
|---|---|
| 개인용 | 올린 사람만. 등록하면 처음엔 전부 여기서 시작합니다 |
| 승인 대기 | 올린 사람만. 관리자 검토 중 |
| 공식 | 모두 |

오케스트레이터가 부를 수 있는 앱은 **공식 앱 전부 + 요청한 본인의 개인용 앱**입니다.
남이 올린 개인용 앱은 절대 불리지 않습니다.

비슷한 역할의 앱이 여러 개면 (예: 사내규정 검색 앱 A 와 B) `capability_tag` 가
같은 것끼리 하나만 골라 씁니다. 본인이 카드에 넣어 둔 앱이 공식 앱보다 우선합니다.

관리자는 `.env` 의 `ADMIN_USER_IDS` 에 사번을 적어 지정합니다.

## 이달의 앱

앱이 불릴 때마다 성공/실패가 기록됩니다. `/stats` 화면에서 월별 순위를 볼 수 있습니다.
순위는 **성공한 호출 수** 기준이라, 많이 불렸어도 계속 실패한 앱은 올라오지 않습니다.
등록자 이름과 연락처도 같이 나오므로 시상과 유지보수 문의에 씁니다.

## 회사에서 이어 개발하기

집에서 만든 것을 회사로 가져가 이어가는 방법, 그리고 폐쇄망 확인 사항은
**[docs/DEPLOY_COMPANY.md](docs/DEPLOY_COMPANY.md)** 에 정리해 두었습니다.

핵심은 하나입니다. **회사에서만 아는 값은 전부 `.env` 와 `config/` 에 있고,
코드는 집과 회사가 같습니다.**

## 폴더

| 폴더 | 무엇 |
|---|---|
| `backend/` | FastAPI. API + 오케스트레이터 + 큐 |
| `frontend/` | Next.js 화면 4개 |
| `templates/` | 개발자가 복사해 쓰는 어댑터 견본 |
| `example_app/` | 기존 앱 + 어댑터 완성 예시 |
| `config/` | 집/회사 프로필, 사내 앱 목록 |
| `docs/` | 규약과 안내 문서 |

구조가 궁금하면 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) 를 보세요.

## 자주 겪는 문제

| 증상 | 확인할 것 |
|---|---|
| `docker compose up` 이 느리다 | 처음 한 번은 이미지를 받느라 몇 분 걸립니다 |
| 화면은 뜨는데 앱 목록이 비어 있다 | `.env` 의 `SEED_FILE` 값과 `/health` 를 확인하세요 |
| 요청 실행이 계속 실패한다 | `.env` 의 `LLM_*` 값. `/health` 에 현재 설정이 보입니다 |
| 등록한 앱이 `unreachable` 이다 | 어댑터가 켜져 있는지, 주소가 `/mcp` 로 끝나는지 |
| 폐쇄망이라 설치가 안 된다 | `.env` 에 `PIP_INDEX_URL`, `NPM_REGISTRY` 를 넣으세요 |

## 기술 스택

Python FastAPI · PostgreSQL · Redis(RQ) · Next.js · Docker Compose ·
Wrapper 규약은 MCP 표준 · LLM 은 OpenAI 호환이면 무엇이든 (사내 Gauss 포함)

외부 인터넷에 의존하는 부분은 없습니다.
