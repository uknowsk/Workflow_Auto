# 공식 앱

앱스토어에 기본으로 올라가는 앱들입니다. 개발자들이 올리는 앱과 똑같이
**Wrapper 규약(MCP)** 대로 만들어져 있고, 등급만 처음부터 `공식(approved)` 입니다.
그래서 여기 있는 세 앱은 "내 앱을 어떻게 붙이는가"의 실제 예시이기도 합니다.

| 앱 | 하는 일 | 주소 | 폴더 |
|---|---|---|---|
| 📝 회의록 정리 | 회의 메모를 요약하고 담당자·기한이 붙은 할 일을 뽑아냄 | `http://app-meeting:9102/mcp` | `meeting/` |
| ✅ 할 일/수명업무 | 할 일과 상급자 지시를 기한과 함께 등록·조회·완료 | `http://app-tasks:9103/mcp` | `tasks/` |
| 📧 사내 메일 | 메일 발송, 회신 여부 확인, 미회신자 리마인드 | `http://app-mail:9101/mcp` | `mail/` |

세 앱은 `docker compose up -d` 로 플랫폼과 함께 뜨고, `config/apps.seed.example.json`
목록에 있어서 서버가 뜰 때 앱스토어에 자동 등록됩니다.

첫 업무 시나리오("회의록 → 할 일 → 담당자 메일 → 회신 리마인드")를 돌려 보는
방법은 [docs/FIRST_SCENARIO.md](../docs/FIRST_SCENARIO.md) 에 있습니다.

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
