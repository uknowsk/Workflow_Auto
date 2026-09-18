"""회의록 정리 앱의 MCP 어댑터 (Wrapper 규약 층).

주의: `from __future__ import annotations` 를 넣지 마세요. MCP 가 인자 타입을
읽지 못합니다.
"""
import os

from mcp.server.fastmcp import FastMCP

import dates
import extract
import store

mcp = FastMCP(
    "회의록 정리",
    instructions=(
        "회의 메모나 녹취 텍스트를 넣으면 요약과 결정사항을 정리하고, "
        "담당자와 기한이 붙은 할 일 목록을 뽑아 줍니다."
    ),
    host=os.getenv("HOST", "0.0.0.0"),
    port=int(os.getenv("PORT", "9102")),
    streamable_http_path="/",
)


@mcp.tool()
def summarize_meeting(
    notes: str,
    title: str = "",
    date: str = "",
    attendees: list[str] = [],
) -> dict:
    """회의 메모나 녹취 텍스트를 요약하고 담당자·기한이 붙은 할 일을 뽑아 저장합니다.

    돌려주는 todos 를 그대로 할 일 앱에 넘기면 할 일이 등록됩니다.

    Args:
        notes: 회의 메모 또는 녹취 텍스트 원문
        title: 회의 제목 (비우면 내용에서 짐작합니다)
        date: 회의 날짜. 예) 2026-09-18 (비우면 오늘)
        attendees: 참석자 목록. 메일을 같이 적으면 담당자 메일이 채워집니다.
            예) ["이하늘 <sky@samsung.com>", "최바다 <sea@samsung.com>"]
    """
    result = extract.organize(notes, title=title, attendees=attendees)
    meeting = store.save(
        title=result["title"],
        date=dates.parse_due(date) or dates.today().isoformat(),
        attendees=list(attendees or []),
        notes=notes,
        summary=result["summary"],
        decisions=result["decisions"],
        todos=result["todos"],
        source=result["source"],
    )
    meeting.pop("notes", None)  # 원문은 저장만 하고 결과에서는 뺍니다(길어서)
    meeting["extracted_by"] = result["source"]
    if result.get("llm_error"):
        meeting["note"] = (
            "LLM 을 쓰지 못해 규칙으로 정리했습니다. 담당자나 기한이 빠질 수 있습니다. "
            f"({result['llm_error']})"
        )
    return meeting


@mcp.tool()
def extract_action_items(notes: str, attendees: list[str] = []) -> dict:
    """회의 메모에서 할 일만 뽑습니다(저장하지 않습니다). 요약이 필요 없을 때 씁니다.

    Args:
        notes: 회의 메모 또는 녹취 텍스트 원문
        attendees: 참석자 목록. 메일을 같이 적으면 담당자 메일이 채워집니다
    """
    result = extract.organize(notes, attendees=attendees)
    return {
        "count": len(result["todos"]),
        "todos": result["todos"],
        "extracted_by": result["source"],
    }


@mcp.tool()
def list_meetings(limit: int = 20) -> dict:
    """정리해 둔 회의록 목록을 최근 것부터 돌려줍니다.

    Args:
        limit: 최대 몇 건까지 (기본 20)
    """
    items = store.recent(limit)
    return {"count": len(items), "meetings": items}


@mcp.tool()
def get_meeting(meeting_id: str) -> dict:
    """회의록 한 건의 요약, 결정사항, 할 일, 원본 메모를 돌려줍니다.

    Args:
        meeting_id: 회의록 id. summarize_meeting 이 돌려준 값
    """
    meeting = store.get(meeting_id)
    if meeting is None:
        return {"found": False, "message": f"{meeting_id} 라는 회의록이 없습니다."}
    return {"found": True, **meeting}
