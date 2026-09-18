"""사내 메일 앱의 MCP 어댑터 (Wrapper 규약 층).

이 앱은 메일을 실제로 내보낼 수 있어 되돌릴 수 없습니다. 그래서 앱스토어에
requires_confirmation: true 로 등록되어, 계획에 끼면 오케스트레이터가 실행 전에
사용자 확인을 받습니다(docs/WRAPPER_SPEC.md 6-1). 집에서는 어댑터가 가짜
메일함이라 아무것도 밖으로 나가지 않습니다.

주의: `from __future__ import annotations` 를 넣지 마세요.
"""
import os

from mcp.server.fastmcp import FastMCP

import compose
import dates
import store
from adapters import get_adapter

mcp = FastMCP(
    "사내 메일",
    instructions=(
        "사내 메일을 보내고, 보낸 메일에 회신이 왔는지 확인하고, "
        "회신하지 않은 사람에게 리마인드 메일을 보냅니다."
    ),
    host=os.getenv("HOST", "0.0.0.0"),
    port=int(os.getenv("PORT", "9101")),
    streamable_http_path="/",
)


def _send_one(to_entry: str, subject: str, body: str, thread_key: str,
              reply_due: str, kind: str = "normal") -> dict:
    """한 사람에게 보내고 기록까지 남깁니다."""
    name, addr = compose.split_address(to_entry)
    adapter = get_adapter()
    provider_id = adapter.send(addr, subject, body)
    return store.record_sent(
        to_addr=addr,
        to_name=name,
        subject=subject,
        body=body,
        thread_key=thread_key,
        reply_due=reply_due,
        kind=kind,
        adapter=adapter.name,
        provider_id=provider_id,
    )


@mcp.tool()
def draft_mail(to: str, subject: str, body: str) -> dict:
    """메일 초안만 만듭니다. 보내지 않습니다. 보내기 전에 문구를 확인할 때 씁니다.

    Args:
        to: 받는 사람. 예) 이하늘 <sky@samsung.com>
        subject: 제목
        body: 본문
    """
    name, addr = compose.split_address(to)
    return {
        "sent": False,
        "to_name": name,
        "to_addr": addr,
        "subject": subject,
        "body": body + compose.footer(),
    }


@mcp.tool()
def send_mail(
    to: list[str],
    subject: str,
    body: str,
    thread_key: str = "",
    reply_due: str = "",
) -> dict:
    """사내 메일을 보냅니다. 회신 기한을 적어 두면 나중에 미회신자를 찾을 수 있습니다.

    Args:
        to: 받는 사람 목록. 예) ["이하늘 <sky@samsung.com>", "sea@samsung.com"]
        subject: 제목
        body: 본문
        thread_key: 같은 건으로 묶는 키. 예) meeting:<회의록id> (회신 추적 단위)
        reply_due: 회신 기한. 예) 2026-09-22 / 3일 뒤 (없으면 비워 두세요)
    """
    sent = [
        _send_one(entry, subject, body + compose.footer(thread_key), thread_key, reply_due)
        for entry in (to or [])
    ]
    return {
        "sent_count": len(sent),
        "adapter": get_adapter().name,
        "mails": [{k: m[k] for k in ("id", "to_name", "to_addr", "reply_due")} for m in sent],
    }


@mcp.tool()
def send_task_mails(
    tasks: list[dict],
    source: str = "",
    thread_key: str = "",
    reply_due: str = "",
    note: str = "",
) -> dict:
    """할 일 목록을 담당자별로 묶어 '할 일 확인' 메일을 각각 보냅니다.

    회의록에서 뽑은 할 일이나 할 일 앱이 돌려준 목록을 그대로 넣으면 됩니다.
    담당자 메일 주소가 없는 할 일은 보내지 않고 목록으로 돌려줍니다.

    Args:
        tasks: 할 일 목록. 각 항목은 {"title": 할 일, "owner": 담당자,
            "owner_email": 담당자 메일, "due": 기한} 형태
        source: 어디서 나온 일인지. 제목과 본문에 들어갑니다. 예) 9/18 주간회의
        thread_key: 같은 건으로 묶는 키. 예) meeting:<회의록id>
        reply_due: 회신 기한. 예) 2026-09-22 / 2일 뒤 (비우면 이틀 뒤)
        note: 본문에 덧붙일 한마디 (없으면 비워 두세요)
    """
    due = dates.parse_due(reply_due) or dates.parse_due("2일 뒤")

    grouped: dict = {}
    missing: list = []
    for task in tasks or []:
        email = str(task.get("owner_email") or task.get("email") or "").strip()
        if not email:
            missing.append(task)
            continue
        key = (str(task.get("owner") or "").strip(), email)
        grouped.setdefault(key, []).append(task)

    sent = []
    for (owner, email), items in grouped.items():
        name = owner or compose.split_address(email)[0]
        subject, body = compose.task_mail(
            name, items, source=source, reply_due=due, note=note, thread_key=thread_key
        )
        mail = _send_one(f"{name} <{email}>", subject, body, thread_key, due)
        sent.append(
            {
                "id": mail["id"],
                "to_name": mail["to_name"],
                "to_addr": mail["to_addr"],
                "task_count": len(items),
                "reply_due": mail["reply_due"],
            }
        )

    return {
        "sent_count": len(sent),
        "adapter": get_adapter().name,
        "reply_due": due,
        "mails": sent,
        "no_email": missing,  # 메일 주소를 몰라 못 보낸 할 일
        "thread_key": thread_key,
    }


@mcp.tool()
def list_sent(thread_key: str = "", limit: int = 30) -> dict:
    """보낸 메일 목록과 회신 여부를 돌려줍니다.

    Args:
        thread_key: 특정 건만 보기. 예) meeting:<회의록id> (비우면 전체)
        limit: 최대 몇 건까지 (기본 30)
    """
    items = store.search(thread_key=thread_key, limit=limit)
    return {"summary": store.thread_summary(thread_key), "mails": items}


@mcp.tool()
def check_replies(thread_key: str = "") -> dict:
    """회신이 왔는지 확인하고, 회신한 사람과 안 한 사람을 나눠 돌려줍니다.

    Args:
        thread_key: 특정 건만 확인. 예) meeting:<회의록id> (비우면 전체)
    """
    pending = [m for m in store.search(thread_key=thread_key, limit=200) if not m["replied"]]

    # 받은 편지함을 읽을 수 있는 어댑터면 새로 온 회신을 먼저 반영합니다.
    fetched = 0
    adapter_note = ""
    try:
        for reply in get_adapter().fetch_replies(pending):
            if reply.get("mail_id"):
                store.mark_replied(reply["mail_id"], reply.get("body", ""))
                fetched += 1
    except NotImplementedError as exc:
        adapter_note = str(exc)
    except Exception as exc:
        adapter_note = f"받은 편지함 확인 실패 - {type(exc).__name__}: {exc}"

    items = store.search(thread_key=thread_key, limit=200)
    result = {
        "summary": store.thread_summary(thread_key),
        "new_replies": fetched,
        "replied": [
            {"to_name": m["to_name"], "to_addr": m["to_addr"], "replied_at": m["replied_at"]}
            for m in items
            if m["replied"]
        ],
        "unreplied": [
            {
                "mail_id": m["id"],
                "to_name": m["to_name"],
                "to_addr": m["to_addr"],
                "reply_due": m["reply_due"],
                "overdue": m["overdue"],
            }
            for m in store.unreplied(thread_key=thread_key)
        ],
    }
    if adapter_note:
        result["note"] = adapter_note
    return result


@mcp.tool()
def list_unreplied(thread_key: str = "", overdue_only: bool = True) -> dict:
    """회신하지 않은 사람 목록을 돌려줍니다. 기본은 회신 기한이 지난 사람만.

    Args:
        thread_key: 특정 건만 보기. 예) meeting:<회의록id> (비우면 전체)
        overdue_only: true=기한이 지난 사람만, false=아직 안 온 사람 전부
    """
    items = store.unreplied(thread_key=thread_key, overdue_only=overdue_only)
    return {
        "count": len(items),
        "people": [
            {
                "mail_id": m["id"],
                "to_name": m["to_name"],
                "to_addr": m["to_addr"],
                "subject": m["subject"],
                "reply_due": m["reply_due"],
                "days_late": -m["days_left"] if m["days_left"] is not None else None,
                "reminder_count": m["reminder_count"],
            }
            for m in items
        ],
    }


@mcp.tool()
def send_reminders(thread_key: str = "", only_overdue: bool = True, note: str = "") -> dict:
    """회신하지 않은 사람에게 리마인드 메일을 보냅니다.

    스케줄러가 매일 이 기능 하나만 부르면 '회신기한이 지난 사람에게 재촉 메일'이
    자동으로 나갑니다.

    Args:
        thread_key: 특정 건만. 예) meeting:<회의록id> (비우면 전체)
        only_overdue: true=회신 기한이 지난 사람에게만, false=아직 안 온 사람 전부
        note: 리마인드 메일에 덧붙일 한마디 (없으면 비워 두세요)
    """
    targets = store.unreplied(thread_key=thread_key, overdue_only=only_overdue)
    sent = []
    for mail in targets:
        subject, body = compose.reminder_mail(mail, note=note)
        reminder = _send_one(
            f"{mail['to_name']} <{mail['to_addr']}>",
            subject,
            body,
            mail["thread_key"],
            mail["reply_due"],
            kind="reminder",
        )
        store.bump_reminder(mail["id"])
        sent.append(
            {
                "to_name": reminder["to_name"],
                "to_addr": reminder["to_addr"],
                "about": mail["subject"],
                "reply_due": mail["reply_due"],
            }
        )
    return {
        "sent_count": len(sent),
        "adapter": get_adapter().name,
        "reminders": sent,
        "message": (
            "리마인드 대상이 없습니다. 모두 회신했거나 기한이 아직 남았습니다."
            if not sent
            else f"{len(sent)}명에게 리마인드를 보냈습니다."
        ),
    }


@mcp.tool()
def mark_replied(mail_id: str, body: str = "") -> dict:
    """보낸 메일에 회신을 받은 것으로 표시합니다.

    전화나 메신저로 답을 받았을 때, 그리고 가짜 메일함으로 시험할 때 씁니다.

    Args:
        mail_id: 보낸 메일 id
        body: 받은 답의 요약 (없으면 비워 두세요)
    """
    mail = store.mark_replied(mail_id, body)
    if mail is None:
        return {"ok": False, "message": f"{mail_id} 라는 보낸 메일이 없습니다."}
    return {"ok": True, "to_name": mail["to_name"], "replied_at": mail["replied_at"]}


@mcp.tool()
def mail_connection_info() -> dict:
    """지금 메일이 실제로 나가는지, 어떤 연결을 쓰는지 알려줍니다.

    가짜 메일함이면 메일이 밖으로 나가지 않습니다.
    """
    return get_adapter().describe()
