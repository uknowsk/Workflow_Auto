"""메일 문구 만들기. 문구를 한 곳에 모아 두면 말투를 바꿀 때 여기만 고치면 됩니다."""
import re

import dates

_ADDR = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def split_address(entry: str) -> tuple[str, str]:
    """ "이하늘 <sky@x.com>" 을 (이름, 주소) 로 나눕니다. 이름이 없으면 주소 앞부분."""
    text = str(entry or "").strip()
    found = _ADDR.search(text)
    addr = found.group(0) if found else text
    name = re.sub(r"[<(\[].*", "", text).strip().rstrip(",")
    if not name or name == addr:
        name = addr.split("@")[0]
    return name, addr


def task_mail(owner_name: str, tasks: list, source: str = "", reply_due: str = "",
              note: str = "", thread_key: str = "") -> tuple[str, str]:
    """담당자 한 명에게 보낼 '할 일 확인' 메일의 제목과 본문."""
    lines = []
    for index, task in enumerate(tasks, start=1):
        title = str(task.get("title") or task.get("task") or "").strip()
        due = str(task.get("due") or "").strip()
        lines.append(f"  {index}. {title}" + (f"  (기한: {due})" if due else ""))

    subject = f"[할 일 확인] {source or '업무'} - {owner_name}님 {len(tasks)}건"
    body = (
        f"안녕하세요, {owner_name}님.\n\n"
        + (f"{source} 에서 정리된 할 일을 전달드립니다.\n\n" if source else "할 일을 전달드립니다.\n\n")
        + "\n".join(lines)
        + "\n\n"
        + (f"{note}\n\n" if note else "")
        + (
            f"확인하셨으면 {reply_due} 까지 회신 부탁드립니다.\n"
            if reply_due
            else "확인하셨으면 회신 부탁드립니다.\n"
        )
        + "\n감사합니다.\n"
        + footer(thread_key)
    )
    return subject, body


def reminder_mail(mail: dict, note: str = "") -> tuple[str, str]:
    """회신이 오지 않은 메일에 보낼 리마인드 메일의 제목과 본문."""
    name = mail.get("to_name") or mail.get("to_addr", "")
    due = mail.get("reply_due") or ""
    left = dates.days_left(due)
    if left is not None and left < 0:
        timing = f"회신 기한({due})이 {abs(left)}일 지났습니다."
    elif left is not None:
        timing = f"회신 기한이 {due} ({left}일 남음) 입니다."
    else:
        timing = "아직 회신을 받지 못했습니다."

    subject = f"[회신 요청] {mail.get('subject', '')}"
    body = (
        f"안녕하세요, {name}님.\n\n"
        f"아래 건에 대해 {timing}\n"
        "확인 후 회신 부탁드립니다.\n\n"
        f"- 제목: {mail.get('subject', '')}\n"
        f"- 보낸 날짜: {str(mail.get('sent_at', ''))[:10]}\n\n"
        + (f"{note}\n\n" if note else "")
        + "감사합니다.\n"
        + footer(mail.get("thread_key", ""))
    )
    return subject, body


def footer(thread_key: str = "") -> str:
    """자동 발송 표시. 나중에 IMAP 으로 회신을 찾을 때 이 건 번호로 짝을 맞춥니다."""
    tail = f" (건: {thread_key})" if thread_key else ""
    return f"\n--\nWorkflow Auto 자동 발송{tail}\n"
