"""첫 업무 시나리오를 LLM 없이 끝까지 돌려 보는 점검 스크립트.

  회의록 정리 -> 할 일 등록 -> 담당자에게 메일 -> 미회신자 리마인드

오케스트레이터(LLM)가 할 일을 사람이 정해진 순서로 대신 부르는 것입니다.
그래서 사내 Gauss 를 아직 안 붙였어도 세 앱이 제대로 이어지는지 확인할 수 있습니다.

쓰는 법 (세 앱이 떠 있어야 합니다. docker compose up -d 로 같이 뜹니다)
    pip install mcp
    python scripts/demo_scenario.py
    python scripts/demo_scenario.py --notes 내회의록.txt

주소가 다르면 환경변수로 바꿉니다.
    MEETING_MCP=http://localhost:9102/mcp TASKS_MCP=... MAIL_MCP=... python scripts/demo_scenario.py
"""
import argparse
import asyncio
import json
import os
from datetime import timedelta
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

MEETING_MCP = os.getenv("MEETING_MCP", "http://localhost:9102/mcp")
TASKS_MCP = os.getenv("TASKS_MCP", "http://localhost:9103/mcp")
MAIL_MCP = os.getenv("MAIL_MCP", "http://localhost:9101/mcp")

SAMPLE = Path(__file__).with_name("sample_meeting.txt")


async def call(endpoint: str, tool: str, arguments: dict) -> dict:
    """앱 하나의 기능 하나를 부릅니다(오케스트레이터가 하는 일과 같습니다)."""
    async with streamablehttp_client(endpoint, headers={}, timeout=60) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                tool, arguments, read_timeout_seconds=timedelta(seconds=60)
            )
            text = "".join(getattr(item, "text", "") for item in result.content)
            if result.isError:
                raise RuntimeError(f"{tool} 실패: {text}")
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"text": text}


def title(step: str, text: str) -> None:
    print(f"\n{'=' * 64}\n{step}  {text}\n{'=' * 64}")


async def main(notes_path: str, remind_all: bool) -> None:
    notes = Path(notes_path).read_text(encoding="utf-8")

    # ── 1. 회의록 정리 ────────────────────────────────────────────────
    title("1단계", "회의록 정리 앱에 회의 메모를 넘깁니다")
    meeting = await call(
        MEETING_MCP,
        "summarize_meeting",
        {"notes": notes, "attendees": []},
    )
    print(f"제목   : {meeting['title']}")
    print(f"정리   : {meeting.get('extracted_by')} (llm=LLM이 정리, rule=규칙으로 정리)")
    print(f"요약   :\n{meeting['summary']}")
    print(f"결정   : {meeting['decisions']}")
    print(f"할 일  : {len(meeting['todos'])}건")
    for todo in meeting["todos"]:
        print(f"  - {todo['owner'] or '담당미정'} / {todo['task']} / 기한 {todo['due'] or '없음'}")

    thread_key = f"meeting:{meeting['id']}"

    # ── 2. 할 일 등록 ────────────────────────────────────────────────
    title("2단계", "뽑아낸 할 일을 할 일 앱에 등록합니다")
    payload = [
        {
            "title": todo["task"],
            "owner": todo["owner"],
            "owner_email": todo["owner_email"],
            "due": todo["due"],
            "source": meeting["title"],
            "source_ref": meeting["id"],
        }
        for todo in meeting["todos"]
    ]
    added = await call(TASKS_MCP, "add_tasks", {"tasks": payload})
    print(f"{added['created_count']}건 등록했습니다.")
    for task in added["created"]:
        print(f"  - [{task['id'][:8]}] {task['owner'] or '담당미정'} / {task['title']}")

    # ── 3. 담당자에게 메일 ──────────────────────────────────────────
    title("3단계", "담당자별로 할 일 확인 메일을 보냅니다")
    mailed = await call(
        MAIL_MCP,
        "send_task_mails",
        {
            "tasks": added["created"],
            "source": meeting["title"],
            "thread_key": thread_key,
            "reply_due": "2일 뒤",
        },
    )
    print(f"연결   : {mailed['adapter']} (mock=가짜 메일함, 실제로는 나가지 않습니다)")
    print(f"발송   : {mailed['sent_count']}통, 회신 기한 {mailed['reply_due']}")
    for mail in mailed["mails"]:
        print(f"  - {mail['to_name']} <{mail['to_addr']}> / 할 일 {mail['task_count']}건")
    if mailed["no_email"]:
        print(f"  (메일 주소를 몰라 못 보낸 할 일 {len(mailed['no_email'])}건)")

    if not mailed["mails"]:
        print("\n보낸 메일이 없어 여기서 멈춥니다. 회의록에 담당자 메일이 있어야 합니다.")
        return

    # ── 4. 한 사람만 회신한 상황 만들기 ────────────────────────────
    title("4단계", "한 사람만 회신한 것으로 표시합니다 (가짜 메일함 시험)")
    first = mailed["mails"][0]
    await call(MAIL_MCP, "mark_replied", {"mail_id": first["id"], "body": "확인했습니다"})
    print(f"{first['to_name']} 님이 회신한 것으로 표시했습니다.")

    # ── 5. 회신 현황 확인 ──────────────────────────────────────────
    title("5단계", "회신 현황을 확인합니다")
    status = await call(MAIL_MCP, "check_replies", {"thread_key": thread_key})
    print(f"현황   : {status['summary']}")
    for person in status["unreplied"]:
        print(f"  미회신: {person['to_name']} / 기한 {person['reply_due']}"
              f" / 기한지남={person['overdue']}")

    # ── 6. 미회신자 리마인드 ───────────────────────────────────────
    title("6단계", "회신하지 않은 사람에게 리마인드 메일을 보냅니다")
    print("(운영에서는 스케줄러가 매일 이 한 줄만 부르면 됩니다:"
          " send_reminders(thread_key, only_overdue=true))")
    reminded = await call(
        MAIL_MCP,
        "send_reminders",
        {"thread_key": thread_key, "only_overdue": not remind_all},
    )
    print(reminded["message"])
    for item in reminded["reminders"]:
        print(f"  - {item['to_name']} <{item['to_addr']}> / 건: {item['about']}")

    title("끝", "시나리오가 끝까지 이어졌습니다")
    print("화면에서 확인: 메일함 http://localhost:3000/mail , 할 일 http://localhost:3000/tasks")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="회의록 -> 할 일 -> 메일 -> 리마인드 점검")
    parser.add_argument("--notes", default=str(SAMPLE), help="회의 메모 파일 (기본: 예시 회의록)")
    parser.add_argument(
        "--only-overdue",
        action="store_true",
        help="리마인드를 회신 기한이 지난 사람에게만 보냅니다(기본은 미회신자 전원)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.notes, remind_all=not args.only_overdue))
