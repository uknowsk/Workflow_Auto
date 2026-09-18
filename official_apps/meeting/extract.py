"""회의록에서 요약과 할 일을 뽑아내는 부분.

두 가지 방법을 씁니다.
  1) LLM (사내 Gauss 등 OpenAI 호환) 에게 시킵니다. 품질이 제일 좋습니다.
  2) LLM 이 없거나 실패하면 규칙으로 뽑습니다. 정확도는 낮지만 절대 멈추지 않습니다.

집에서 LLM 없이 시나리오를 끝까지 돌려볼 수 있어야 해서 2번을 같이 뒀습니다.
결과의 source 값("llm" / "rule")으로 어느 쪽이었는지 알 수 있습니다.
"""
import json
import os
import re

import httpx

import dates

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))

_PROMPT = """너는 회의록을 정리하는 비서다. 아래 회의 메모를 읽고 JSON 하나만 출력해라.

{{
  "title": "회의 제목",
  "summary": "회의 내용 요약. 3~6문장, 한국어",
  "decisions": ["결정된 사항 1", "결정된 사항 2"],
  "todos": [
    {{"task": "해야 할 일", "owner": "담당자 이름", "owner_email": "메일주소 또는 빈 문자열", "due": "YYYY-MM-DD 또는 빈 문자열"}}
  ]
}}

규칙
- 오늘은 {today} 다. "다음주 월요일" 같은 표현은 실제 날짜로 바꿔라.
- 회의록에 없는 담당자나 기한을 상상해서 넣지 마라. 모르면 빈 문자열.
- JSON 외에 다른 말은 절대 쓰지 마라.

참석자 정보: {attendees}

회의 메모
---
{notes}
---"""

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_NAME_HEAD = re.compile(r"^([가-힣]{2,4})\s*(?:님|씨|책임|선임|부장|과장|차장|팀장|대리)?\s*[:：]")
_OWNER_WORD = re.compile(r"담당\s*[:：]?\s*([가-힣]{2,4})")
_PAREN_NAME = re.compile(r"\(([가-힣]{2,4})\s*(?:님|책임|선임)?\)")
_DUE_CHUNK = re.compile(
    r"(\d{4}[-./]\d{1,2}[-./]\d{1,2}"
    r"|\d{1,2}\s*월\s*\d{1,2}\s*일"
    r"|\d{1,2}/\d{1,2}"
    r"|다음\s*주\s*[월화수목금토일]요일"
    r"|[월화수목금토일]요일"
    r"|오늘|내일|모레"
    r"|\d+\s*(?:영업)?일\s*(?:뒤|후|내|이내))"
)
_ACTION_WORDS = (
    "하기로", "해야", "작성", "확인", "공유", "준비", "검토", "정리", "회신",
    "제출", "수정", "보완", "조사", "협의", "전달", "취합", "완료", "요청",
    "예정", "진행", "반영", "테스트", "배포",
)
_DECISION_WORDS = ("결정", "합의", "확정", "승인")
# "참석: ...", "일시: ..." 처럼 사람 이름이 아닌 머리말. 할 일로 잡으면 안 됩니다.
_META_HEADS = {
    "참석", "참석자", "불참", "일시", "장소", "회의", "회의록", "안건", "주제",
    "목적", "작성", "작성자", "비고", "기타", "다음",
}


def _strip_bullet(line: str) -> str:
    return re.sub(r"^\s*(?:[-*•·]|\d+[.)])\s*", "", line).strip()


def attendee_emails(attendees: list) -> dict:
    """참석자 목록에서 '이름 -> 메일' 표를 만듭니다. 예) "이하늘 <sky@x.com>" """
    table: dict = {}
    for entry in attendees or []:
        text = str(entry)
        mail = _EMAIL.search(text)
        name = re.sub(r"[<(].*", "", text).strip()
        name = re.sub(r"(님|씨|책임|선임|부장|과장|차장|팀장|대리)$", "", name).strip()
        if name and mail:
            table[name] = mail.group(0)
    return table


def _emails_in_notes(notes: str) -> dict:
    """회의록 본문에 "이하늘(sky@x.com)" 처럼 적힌 메일을 주워 담습니다."""
    table: dict = {}
    for match in re.finditer(r"([가-힣]{2,4})\s*[<(\[]\s*(" + _EMAIL.pattern + r")", notes):
        table[match.group(1)] = match.group(2)
    return table


def by_rules(notes: str, title: str = "", attendees: list | None = None) -> dict:
    """LLM 없이 규칙으로 뽑습니다. 못 잡는 것도 있지만 항상 동작합니다."""
    directory = {**_emails_in_notes(notes), **attendee_emails(attendees or [])}
    lines = [_strip_bullet(line) for line in (notes or "").splitlines()]
    lines = [line for line in lines if line]

    decisions: list = []
    todos: list = []
    for line in lines:
        if any(word in line for word in _DECISION_WORDS):
            decisions.append(line)

        head = _NAME_HEAD.search(line)
        head_word = head.group(1) if head else ""
        if head_word in _META_HEADS:
            continue  # 참석·일시·장소 같은 머리말 줄은 할 일이 아닙니다

        owner = ""
        owner_word = _OWNER_WORD.search(line)
        if owner_word:  # "담당: 김로아" 가 이름 머리말보다 확실합니다
            owner = owner_word.group(1)
        elif head_word:
            owner = head_word
        elif _PAREN_NAME.search(line):
            owner = _PAREN_NAME.search(line).group(1)

        chunk = _DUE_CHUNK.search(line)
        due = dates.parse_due(chunk.group(1)) if chunk else ""

        looks_like_todo = owner or any(word in line for word in _ACTION_WORDS)
        if not looks_like_todo or any(word in line for word in _DECISION_WORDS):
            continue

        task = line
        if head and owner == head_word:
            task = line[head.end():]
        task = _OWNER_WORD.sub("", task, count=1)  # "담당: 김로아" 는 본문에서 지웁니다
        task = re.sub(r"^\s*[-–:：]\s*", "", task).strip()
        if not task:
            continue
        todos.append(
            {
                "task": task,
                "owner": owner,
                "owner_email": directory.get(owner, ""),
                "due": due,
            }
        )

    summary_lines = decisions[:2] + [t["task"] for t in todos[:4]]
    if not summary_lines:
        summary_lines = lines[:4]
    summary = "\n".join(f"- {line}" for line in summary_lines)

    return {
        "title": title or (lines[0][:80] if lines else "회의"),
        "summary": summary,
        "decisions": decisions,
        "todos": todos,
        "source": "rule",
    }


def by_llm(notes: str, title: str = "", attendees: list | None = None) -> dict:
    """LLM 에게 정리를 시킵니다. 실패하면 예외를 던집니다(호출한 쪽이 규칙으로 넘어감)."""
    if not (LLM_BASE_URL and LLM_MODEL):
        raise RuntimeError("LLM 설정(LLM_BASE_URL, LLM_MODEL)이 없습니다.")

    prompt = _PROMPT.format(
        today=dates.today().isoformat(),
        attendees=", ".join(str(a) for a in (attendees or [])) or "(없음)",
        notes=notes,
    )
    response = httpx.post(
        f"{LLM_BASE_URL.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {LLM_API_KEY}"},
        json={
            "model": LLM_MODEL,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=LLM_TIMEOUT,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]

    start, end = content.find("{"), content.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("LLM 이 JSON 을 주지 않았습니다.")
    parsed = json.loads(content[start : end + 1])

    directory = {**_emails_in_notes(notes), **attendee_emails(attendees or [])}
    todos = []
    for item in parsed.get("todos") or []:
        owner = str(item.get("owner") or "").strip()
        todos.append(
            {
                "task": str(item.get("task") or "").strip(),
                "owner": owner,
                "owner_email": str(item.get("owner_email") or "").strip()
                or directory.get(owner, ""),
                "due": dates.parse_due(str(item.get("due") or "")),
            }
        )

    return {
        "title": str(parsed.get("title") or title or "회의"),
        "summary": str(parsed.get("summary") or ""),
        "decisions": [str(d) for d in (parsed.get("decisions") or [])],
        "todos": [t for t in todos if t["task"]],
        "source": "llm",
    }


def organize(notes: str, title: str = "", attendees: list | None = None) -> dict:
    """LLM 을 먼저 시도하고, 안 되면 규칙으로 정리합니다."""
    try:
        return by_llm(notes, title=title, attendees=attendees)
    except Exception as exc:  # 회의록 정리가 아예 안 되는 것보다는 낫습니다
        result = by_rules(notes, title=title, attendees=attendees)
        result["llm_error"] = f"{type(exc).__name__}: {exc}"[:300]
        return result
