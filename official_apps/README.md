# 공식 앱 (official_apps)

앱스토어에 기본으로 올라가는 앱 10개입니다. 개발자들이 각자 올리는 앱과 똑같은
**Wrapper 규약(MCP)** 을 지키고, 등급만 처음부터 `공식(approved)` 입니다.
즉 이 폴더는 "플랫폼의 첫 손님"이자, 남들이 자기 앱을 만들 때 따라 볼 수 있는
실물 예시입니다.

**첫 업무 시나리오용 앱 3개** — `config/apps.seed.example.json` 로 등록됩니다.

| 앱 | 하는 일 | 주소 | 폴더 |
|---|---|---|---|
| 📝 회의록 정리 | 회의 메모를 요약하고 담당자·기한이 붙은 할 일을 뽑아냄 | `http://app-meeting:9102/mcp` | `meeting/` |
| ✅ 할 일/수명업무 | 할 일과 상급자 지시를 기한과 함께 등록·조회·완료 | `http://app-tasks:9103/mcp` | `tasks/` |
| 📧 사내 메일 | 메일 발송, 회신 여부 확인, 미회신자 리마인드 | `http://app-mail:9101/mcp` | `mail/` |

**업무 도구 앱 7개** — `config/apps.seed.official.json` 로 등록됩니다.
이 7개는 이미지 하나를 공유하고, `common/` 폴더의 공용 코드를 씁니다.

| 앱 | 하는 일 | 주소 | 폴더 |
|---|---|---|---|
| 📁 개발 프로젝트 관리 | 내 프로젝트 등록, 단계별 산출물 안내, **양식 채워 산출물 초안 만들기** | `:9111` | `dev_projects/` |
| 🏅 업적 정리 | 한 일을 모아 고과 제출용 근거자료로 정리 | `:9112` | `achievements/` |
| 🗓️ 주간보고 자동 생성 | 이번 주 기록을 모아 주간보고 초안, 월간 요약 | `:9113` | `weekly_report/` |
| 🧮 도구 모음 | 계산기, 단위 변환, 세계 시계, 근무일 계산 | `:9114` | `toolbox/` |
| 🤝 회의 일정 조율 | 후보 시간 취합, 가능한 사람 많은 시간 찾기, 안내문 초안 | `:9115` | `meeting_scheduler/` |
| 📋 결재/승인 추적 | 올린 결재가 어디서 며칠째 멈췄는지 | `:9116` | `approvals/` |
| 📝 문서 요약/번역 | 긴 문서 요약, 한 장 요약, 한↔영 번역 | `:9117` | `docs_assistant/` |

> 포트가 9101~9103 과 9111~9117 로 나뉜 이유: 두 묶음이 같은 서버에서 동시에
> 뜨기 때문에 번호가 겹치면 안 됩니다.

전부 `docker compose up -d --build` 로 플랫폼과 함께 뜹니다.
첫 업무 시나리오("회의록 → 할 일 → 담당자 메일 → 회신 리마인드")를 돌려 보는
방법은 [docs/FIRST_SCENARIO.md](../docs/FIRST_SCENARIO.md) 에 있습니다.

## 어떻게 켜지나

`docker compose up -d --build` 하면 7개가 같이 뜨고, 서버가 시작할 때
`config/apps.seed.official.json` 을 읽어 앱스토어에 자동 등록됩니다.
화면(http://localhost:3000)의 앱스토어에서 바로 보입니다.

이미지는 **하나**입니다. 컨테이너마다 `command` 로 어떤 앱을 띄울지만 다릅니다.

```bash
# 하나만 따로 돌려보기
cd official_apps
pip install -r requirements.txt
PORT=9114 python -m toolbox.server     # http://localhost:9114/mcp
```

## 폴더

```
common/          여러 앱이 같이 쓰는 것들
  store.py         앱마다 SQLite 파일 하나. 기록을 넣고 빼는 창고
  dates.py         날짜 문자열 다루기
  office.py        엑셀·워드·PPT 양식에 값 채우기
dev_projects/    개발 프로젝트 관리 (+ forms/ 기본 양식)
achievements/    업적 정리
weekly_report/   주간보고
toolbox/         계산기·단위변환·세계시계
meeting_scheduler/ 회의 일정 조율
approvals/       결재 추적
docs_assistant/  문서 요약·번역 (사내 LLM 사용)

meeting/         회의록 정리   (시나리오 앱, 자기 이미지·requirements 를 따로 씀)
tasks/           할 일/수명업무 (시나리오 앱)
mail/            사내 메일     (시나리오 앱, adapters/ 로 mock↔smtp 전환)
```

## 양식에 내용 채우기 (개발 프로젝트 앱)

양식 파일 안에 `{{항목}}` 이라고 적어 두면 그 자리에 값이 들어갑니다.

```
요구사항정의서.docx 안:   작성자: {{author}}
                ↓
fill_form({"author": "김로아"}, form_key="요구사항정의서")
                ↓
요구사항정의서.docx:      작성자: 김로아
```

| 양식 형식 | 결과 |
|---|---|
| `.md` `.txt` `.csv` | 채운 내용을 **글로** 돌려줍니다 |
| `.xlsx` `.docx` `.pptx` | 서식을 그대로 둔 채 값만 채워 **파일**을 만들고 내려받기 주소를 돌려줍니다 |

엑셀은 수식이 든 칸을 건드리지 않고, 워드는 한 문장이 여러 조각으로 쪼개져
저장돼 있어도 찾아서 바꿉니다. 채우지 못한 항목은 `missing` 으로 알려 주므로
그 값만 보태서 다시 부르면 됩니다.

양식은 두 군데서 옵니다.

1. `dev_projects/forms/` — 기본으로 들어 있는 양식 (요구사항정의서, 시스템설계서,
   시험결과서, 완료보고서, 주간보고서.xlsx). `FORMS_DIR` 로 회사 양식 폴더를
   가리키면 통째로 바꿀 수 있습니다.
2. 플랫폼 **양식 저장소** — `.env` 에 `WORKFLOW_API_BASE` 를 채우면 저장소에
   올려 둔 양식도 목록에 같이 나오고, `platform:<양식id>` 로 골라 쓸 수 있습니다.

## 설정값

| 환경변수 | 기본값 | 무엇 |
|---|---|---|
| `PORT` | 앱마다 다름 | 이 앱이 쓸 포트 |
| `DATA_DIR` | `./data` | 기록과 만들어진 파일을 두는 곳 |
| `PUBLIC_BASE_URL` | `http://localhost:9111` | 채운 파일 내려받기 주소 |
| `FORMS_DIR` | `dev_projects/forms` | 기본 양식 폴더 |
| `WORKFLOW_API_BASE` | (비움) | 플랫폼 양식 저장소 주소 |
| `WORKFLOW_API_TOKEN` / `WORKFLOW_API_USER` | (비움) | 저장소를 읽을 때 쓰는 인증 |
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | .env | 문서 요약·번역 앱이 쓰는 사내 LLM |

외부 인터넷에 나가는 부분은 없습니다. 파일은 SQLite 하나에 쌓이므로
별도 DB 서버도 필요 없습니다.

## 테스트

```bash
cd official_apps
pip install -r requirements-dev.txt
pytest tests -q
```

양식 채우기(엑셀 수식 보존, 워드의 쪼개진 문장 처리)와 앱별 핵심 동작을 확인합니다.
테스트는 임시 폴더를 쓰므로 실제 기록을 건드리지 않습니다.

## 다른 앱과 이어 쓰기

앱끼리 서로 직접 부르지 않습니다. **오케스트레이터가 가운데서 이어 줍니다.**

```
"이번 달 한 일 정리해서 고과 자료 만들어줘"
   → 할 일 앱: 완료 목록 조회
   → 업적 정리 앱: import_achievements 로 받아 쌓기
   → 업적 정리 앱: summarize_period 로 정리 문서 생성
```

그래서 업적 정리 앱과 주간보고 앱에는 "다른 앱의 기록을 받아 넣는" 기능
(`import_achievements`, `collect_records`)이 있습니다. 메일·회의록·할 일 앱이
붙으면 그대로 이어집니다.

메일 발송처럼 되돌릴 수 없는 일은 이 앱들이 하지 않습니다. 회의 확정 안내문,
리마인드 메일은 **초안까지만** 만들고 발송은 메일 앱이 맡습니다.

---

## 시나리오 앱 3개 자세히

## 앱 하나의 구조

```
mail/
  server.py        ← 실행 파일. /mcp (오케스트레이터용) 와 /api (화면용) 를 같이 띄움
  mcp_adapter.py   ← Wrapper 규약 층. 기능 하나 = 함수 하나
  store.py         ← 이 앱의 데이터 (SQLite 파일 하나)
  compose.py       ← 메일 문구
  adapters/        ← 메일을 실제로 내보내는 부분 (갈아끼우는 곳)
  workflow_app.json← 앱스토어 등록 정보 (매니페스트)
```

플랫폼 DB(PostgreSQL)를 쓰지 않고 각자 SQLite 파일을 씁니다. 등록된 앱은
플랫폼과 느슨하게만 붙어 있어야 하기 때문입니다(남의 앱도 마찬가지입니다).

> 이미 만들어진 앱을 붙일 때는 앱을 고치지 말고 옆에 어댑터만 두세요
> (`templates/mcp_adapter_http/`, `example_app/` 참고). 위 구조는 앱을 처음부터
> 만들 때의 모습입니다.

## 사내 메일은 왜 어댑터인가

삼성 사내 메일(Knox 메일)이 프로그램 발송용으로 무엇을 열어 주는지 아직
확인되지 않았습니다. 그래서 "실제로 내보내는 부분"만 떼어 두었습니다.

| `.env` 의 `MAIL_ADAPTER` | 무슨 일이 일어나나 |
|---|---|
| `mock` (기본) | **실제로 보내지 않습니다.** 앱 DB에 쌓이고 `/mail` 화면에서 보입니다 |
| `smtp` | 사내 SMTP/IMAP 으로 실제 발송. 값 확인 후 `mail/adapters/smtp_imap.py` 를 채우면 동작 |

집에서는 `mock` 으로 시나리오 전체를 검증하고, 회사에서는 어댑터 하나만
갈아끼웁니다. 앱의 나머지(도구, 회신 추적, 리마인드, 화면)는 그대로 돕니다.

회사 IT/메일 담당에게 확인할 것은 세 가지입니다.

1. 발송용 SMTP 서버 주소/포트와 인증 방식이 있는지
2. 발송용 API(REST 등)를 따로 주는지
3. 회신 확인을 위해 받은 편지함을 읽는 방법(IMAP 등)이 열려 있는지

## 메일은 되돌릴 수 없으니

사내 메일 앱은 `requires_confirmation: true` 로 등록됩니다. 이 앱이 계획에 끼면
오케스트레이터가 **바로 실행하지 않고 계획을 보여 주며 멈춥니다**. 사용자가
"이대로 진행"을 눌러야 메일이 나갑니다 (docs/WRAPPER_SPEC.md 6-1).

메일을 보내지 않고 문구만 확인하고 싶으면 `draft_mail` 기능을 쓰면 됩니다.

받은 메일(회신) 본문은 **자료로만** 씁니다. 회신 여부를 표시하는 데만 쓰고,
본문에 적힌 말이 받는 사람이나 발송 여부를 정하게 하지 않습니다. 누구나 사내
메일을 보낼 수 있으므로, 메일 본문을 오케스트레이터의 지시로 삼으면 위험합니다.

## 앱별 기능 목록

### 📝 회의록 정리 (`meeting-notes`)

| 기능 | 하는 일 |
|---|---|
| `summarize_meeting` | 회의 메모를 요약하고 할 일을 뽑아 저장. 결과의 `todos` 를 할 일 앱에 그대로 넘길 수 있음 |
| `extract_action_items` | 할 일만 뽑기 (저장 안 함) |
| `list_meetings` / `get_meeting` | 정리해 둔 회의록 목록/상세 |

요약은 사내 Gauss(LLM)로 합니다. **LLM 이 없거나 실패하면 규칙으로 뽑습니다.**
그래서 LLM 없이도 멈추지 않습니다. 결과의 `extracted_by` 가 `llm` 인지 `rule`
인지로 어느 쪽이었는지 알 수 있습니다(규칙 쪽은 담당자나 기한을 놓칠 수 있습니다).

### ✅ 할 일/수명업무 (`task-tracker`)

| 기능 | 하는 일 |
|---|---|
| `add_task` / `add_tasks` | 할 일 한 건 / 여러 건 등록 |
| `add_order` | 상급자에게 지시받은 수명업무 등록 (지시자와 기한 포함) |
| `list_tasks` | 목록 (담당자·상태·종류로 걸러내기) |
| `complete_task` | 완료 처리 |
| `list_due_soon` | 기한 임박 + 이미 지난 일 |

기한은 `2026-09-25` 뿐 아니라 `9월 25일`, `내일`, `3일 뒤`, `다음주 월요일`
같은 말도 알아듣고 날짜로 바꿔 저장합니다.

### 📧 사내 메일 (`intra-mail`)

| 기능 | 하는 일 |
|---|---|
| `draft_mail` | 초안만 만들기 (보내지 않음) |
| `send_mail` | 메일 보내기 |
| `send_task_mails` | 할 일 목록을 **담당자별로 묶어** 확인 메일 발송 |
| `list_sent` / `check_replies` | 보낸 메일과 회신 현황 |
| `list_unreplied` | 회신하지 않은 사람 목록 |
| `send_reminders` | **미회신자에게 리마인드 발송** (스케줄러가 부를 기능) |
| `mark_replied` | 회신 받은 것으로 표시 (전화로 답을 받았을 때, 가짜 메일함 시험용) |
| `mail_connection_info` | 지금 실제로 메일이 나가는 설정인지 확인 |

회신 추적은 `thread_key`(예: `meeting:<회의록id>`) 단위로 묶습니다. 같은 건으로
보낸 메일만 모아 "누가 답을 안 했나"를 셀 수 있습니다.

## 화면

| 주소 | 무엇 |
|---|---|
| http://localhost:3000/mail | 메일함. 보낸 메일, 회신 여부, 리마인드 버튼 |
| http://localhost:3000/tasks | 할 일/수명업무 목록, 완료 버튼, 직접 추가 |

## 따로 돌려 보기

플랫폼 없이 앱 하나만 켜 볼 수도 있습니다.

```bash
cd official_apps/tasks
pip install -r requirements.txt
TASKS_DB=./tasks.db PORT=9103 python server.py
# http://localhost:9103/docs  화면용 API 문서
# http://localhost:9103/mcp   오케스트레이터가 부르는 주소
```
