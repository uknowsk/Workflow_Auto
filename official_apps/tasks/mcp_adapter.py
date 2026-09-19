"""할 일/수명업무 앱의 MCP 어댑터 (Wrapper 규약 층).

오케스트레이터는 이 파일에 적힌 기능 설명만 보고 "지금 이 기능을 쓸까?"를
판단합니다. 그래서 docstring 첫 줄을 제일 공들여 썼습니다.
규약은 docs/WRAPPER_SPEC.md 참고.

주의: 이 파일에 `from __future__ import annotations` 를 넣으면 MCP 가 인자
타입을 읽지 못합니다. 넣지 마세요.
"""
import os

from mcp.server.fastmcp import FastMCP

import store

mcp = FastMCP(
    "할 일/수명업무 관리",
    instructions=(
        "할 일과 상급자에게 지시받은 수명업무를 기한과 담당자와 함께 등록하고, "
        "목록을 보거나 완료 처리하고, 기한이 임박했거나 지난 일을 찾습니다."
    ),
    host=os.getenv("HOST", "0.0.0.0"),
    port=int(os.getenv("PORT", "9103")),
    streamable_http_path="/",
)


@mcp.tool()
def add_task(
    title: str,
    owner: str = "",
    owner_email: str = "",
    due: str = "",
    note: str = "",
    source: str = "",
    source_ref: str = "",
) -> dict:
    """할 일 하나를 담당자와 기한과 함께 등록합니다.

    Args:
        title: 할 일 내용. 예) API 규격서 초안 작성
        owner: 담당자 이름. 예) 이하늘
        owner_email: 담당자 메일 주소. 메일로 알릴 때 씁니다
        due: 기한. 예) 2026-09-25 / 9월 25일 / 내일 / 3일 뒤
        note: 참고 사항 (없으면 비워 두세요)
        source: 이 일이 나온 곳. 예) 9/18 주간회의
        source_ref: 연결 고리. 예) 회의록 앱이 돌려준 meeting_id
    """
    return store.add(
        title=title,
        owner=owner,
        owner_email=owner_email,
        due=due,
        note=note,
        source=source,
        source_ref=source_ref,
    )


@mcp.tool()
def add_tasks(tasks: list[dict]) -> dict:
    """할 일 여러 개를 한 번에 등록합니다. 회의록에서 뽑은 할 일 목록을 그대로 넣으면 됩니다.

    Args:
        tasks: 할 일 목록. 각 항목은
            {"title": 할 일, "owner": 담당자, "owner_email": 메일,
             "due": 기한, "note": 참고, "source": 출처, "source_ref": 연결고리}
            형태이며 title 만 필수입니다.
    """
    created: list[dict] = []
    skipped: list[dict] = []
    for item in tasks or []:
        title = str(item.get("title") or item.get("task") or "").strip()
        if not title:
            skipped.append(item)
            continue
        created.append(
            store.add(
                title=title,
                owner=str(item.get("owner") or ""),
                owner_email=str(item.get("owner_email") or item.get("email") or ""),
                due=str(item.get("due") or ""),
                note=str(item.get("note") or ""),
                source=str(item.get("source") or ""),
                source_ref=str(item.get("source_ref") or ""),
            )
        )
    return {"created_count": len(created), "created": created, "skipped": skipped}


@mcp.tool()
def add_order(
    title: str,
    orderer: str,
    due: str = "",
    owner: str = "",
    owner_email: str = "",
    note: str = "",
) -> dict:
    """상급자에게 지시받은 수명업무를 등록합니다. 지시한 사람과 기한을 같이 남깁니다.

    Args:
        title: 지시받은 일. 예) 하반기 품질지표 정리해서 보고
        orderer: 지시한 상급자. 예) 박부장
        due: 기한. 예) 2026-09-30 / 다음주 월요일
        owner: 실제로 할 사람 (내가 할 일이면 비워 두세요)
        owner_email: 담당자 메일 주소
        note: 참고 사항
    """
    return store.add(
        title=title,
        owner=owner,
        owner_email=owner_email,
        due=due,
        note=note,
        kind="order",
        orderer=orderer,
    )


@mcp.tool()
def list_tasks(owner: str = "", status: str = "open", kind: str = "all", limit: int = 50) -> dict:
    """등록된 할 일과 수명업무 목록을 기한 순으로 돌려줍니다.

    Args:
        owner: 담당자 이름으로 걸러내기 (비우면 전체)
        status: open=아직 안 한 일, done=끝낸 일, all=전부
        kind: task=할 일, order=수명업무, all=전부
        limit: 최대 몇 건까지 (기본 50)
    """
    items = store.search(owner=owner, status=status, kind=kind, limit=limit)
    return {"count": len(items), "tasks": items}


@mcp.tool()
def complete_task(task_id: str) -> dict:
    """할 일 하나를 '완료'로 표시합니다.

    Args:
        task_id: 등록할 때 돌려받은 할 일 id
    """
    task = store.complete(task_id)
    if task is None:
        return {"ok": False, "message": f"{task_id} 라는 할 일이 없습니다."}
    return {"ok": True, "task": task}


@mcp.tool()
def list_due_soon(days: int = 3, owner: str = "") -> dict:
    """기한이 며칠 안 남은 일과 이미 기한이 지난 일을 찾습니다. 리마인드할 대상을 고를 때 씁니다.

    Args:
        days: 며칠 안으로 다가온 것까지 볼지. 기본 3일
        owner: 담당자 이름으로 걸러내기 (비우면 전체)
    """
    items = store.due_soon(days=days, owner=owner)
    overdue = [t for t in items if t["overdue"]]
    return {
        "count": len(items),
        "overdue_count": len(overdue),
        "tasks": items,
    }
