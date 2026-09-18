"""결재/승인 추적 앱 - 내가 올린 건이 어디서 며칠째 멈춰 있는지 봅니다.

사내 결재 시스템을 대신하지 않습니다. 결재를 올리는 것도, 승인하는 것도
원래 시스템에서 합니다. 이 앱은 "내가 올린 것들이 지금 어디에 있나"를
한눈에 보고, 오래 멈춘 건을 짚어 주는 수첩 역할만 합니다.

실행:  python -m approvals.server   ->  http://localhost:9106/mcp
"""
import os

from mcp.server.fastmcp import FastMCP

from common.dates import days_between
from common.store import Store, today_iso

store = Store("approvals")

mcp = FastMCP(
    "결재/승인 추적",
    instructions="내가 올린 결재·승인 요청의 현재 단계와 며칠째 멈춰 있는지를 등록/조회합니다.",
    host=os.getenv("HOST", "0.0.0.0"),
    port=int(os.getenv("PORT", "9106")),
)

OPEN_STATUS = "진행중"


def _decorate(record: dict) -> dict:
    """며칠째 멈춰 있는지 계산해 붙입니다."""
    since = record.get("step_since") or record.get("submitted_on") or record.get("created_at", "")[:10]
    record["days_at_step"] = max(0, days_between(since))
    record["days_since_submit"] = max(0, days_between(record.get("submitted_on", since)))
    return record


@mcp.tool()
def register_approval(
    user_id: str,
    title: str,
    current_step: str,
    approver: str = "",
    doc_no: str = "",
    submitted_on: str = "",
    due_date: str = "",
    note: str = "",
) -> dict:
    """내가 올린 결재/승인 건을 등록합니다.

    Args:
        user_id: 사번. 예) E1001
        title: 결재 제목. 예) 개발 장비 구매 요청
        current_step: 지금 어느 단계에 있는지. 예) 팀장 검토
        approver: 지금 결재자. 예) 박부장
        doc_no: 결재 문서번호. 예) 2026-구매-0032
        submitted_on: 상신일. 비우면 오늘. 예) 2026-09-15
        due_date: 이때까지는 끝나야 하는 날. 예) 2026-09-25
        note: 메모
    """
    submitted = (submitted_on or today_iso())[:10]
    return _decorate(store.put(
        "approval",
        {
            "title": title,
            "doc_no": doc_no,
            "current_step": current_step,
            "approver": approver,
            "submitted_on": submitted,
            "step_since": submitted,
            "due_date": due_date,
            "status": OPEN_STATUS,
            "note": note,
            "history": [{"date": submitted, "step": current_step, "approver": approver}],
        },
        user_id=user_id,
    ))


@mcp.tool()
def update_approval_step(
    approval_id: str,
    current_step: str,
    approver: str = "",
    changed_on: str = "",
    note: str = "",
) -> dict:
    """결재가 다음 단계로 넘어갔을 때 현재 단계를 갱신합니다. 이동 기록도 남습니다.

    Args:
        approval_id: 결재 건 id
        current_step: 새 단계. 예) 담당임원 결재
        approver: 새 결재자. 예) 정상무
        changed_on: 넘어간 날. 비우면 오늘
        note: 메모
    """
    record = store.get(approval_id)
    if record is None or record.get("kind") != "approval":
        return {"ok": False, "error": f"결재 건을 찾을 수 없습니다: {approval_id}"}

    moved = (changed_on or today_iso())[:10]
    history = list(record.get("history", []))
    history.append({"date": moved, "step": current_step, "approver": approver})
    updated = store.update(
        approval_id,
        current_step=current_step,
        approver=approver or record.get("approver", ""),
        step_since=moved,
        history=history,
        note=note or record.get("note", ""),
    )
    return {"ok": True, "approval": _decorate(updated)}


@mcp.tool()
def complete_approval(approval_id: str, result: str, completed_on: str = "", note: str = "") -> dict:
    """결재가 끝났을 때 결과를 적어 마감합니다.

    Args:
        approval_id: 결재 건 id
        result: 승인 / 반려 / 취소
        completed_on: 끝난 날. 비우면 오늘
        note: 반려 사유 등 메모
    """
    record = store.get(approval_id)
    if record is None or record.get("kind") != "approval":
        return {"ok": False, "error": f"결재 건을 찾을 수 없습니다: {approval_id}"}

    finished = (completed_on or today_iso())[:10]
    history = list(record.get("history", []))
    history.append({"date": finished, "step": f"완료({result})", "approver": record.get("approver", "")})
    updated = store.update(
        approval_id,
        status=result,
        completed_on=finished,
        current_step=f"완료({result})",
        history=history,
        note=note or record.get("note", ""),
    )
    return {"ok": True, "approval": updated}


@mcp.tool()
def list_approvals(user_id: str, only_open: bool = True) -> dict:
    """내가 올린 결재 건 목록을, 오래 멈춘 것부터 돌려줍니다.

    Args:
        user_id: 사번. 예) E1001
        only_open: 아직 안 끝난 건만 볼지. 기본 True
    """
    records = [_decorate(r) for r in store.list("approval", user_id=user_id)]
    if only_open:
        records = [r for r in records if r.get("status") == OPEN_STATUS]
    records.sort(key=lambda r: -r["days_at_step"])
    return {
        "count": len(records),
        "approvals": [
            {
                "approval_id": r["id"],
                "title": r.get("title"),
                "doc_no": r.get("doc_no", ""),
                "current_step": r.get("current_step"),
                "approver": r.get("approver", ""),
                "status": r.get("status"),
                "submitted_on": r.get("submitted_on", ""),
                "days_at_step": r["days_at_step"],
                "days_since_submit": r["days_since_submit"],
                "due_date": r.get("due_date", ""),
            }
            for r in records
        ],
    }


@mcp.tool()
def stalled_approvals(user_id: str, days: int = 3) -> dict:
    """며칠 이상 같은 단계에 멈춰 있는 결재 건만 골라 줍니다.

    "부장님 책상에서 일주일째 자고 있는 건"을 찾을 때 씁니다.

    Args:
        user_id: 사번. 예) E1001
        days: 며칠 이상 멈춘 것을 볼지. 기본 3일
    """
    found = list_approvals(user_id, only_open=True)
    stalled = [a for a in found["approvals"] if a["days_at_step"] >= max(1, days)]
    overdue = [
        a for a in found["approvals"]
        if a.get("due_date") and days_between(a["due_date"]) > 0
    ]
    return {
        "threshold_days": days,
        "stalled_count": len(stalled),
        "stalled": stalled,
        "overdue": overdue,
        "summary": (
            f"{len(stalled)}건이 {days}일 이상 멈춰 있고, {len(overdue)}건은 기한이 지났습니다."
            if stalled or overdue
            else "오래 멈춰 있거나 기한이 지난 결재는 없습니다."
        ),
    }


@mcp.tool()
def approval_history(approval_id: str) -> dict:
    """결재 건 하나가 어떤 단계들을 거쳐 왔는지 보여줍니다.

    Args:
        approval_id: 결재 건 id
    """
    record = store.get(approval_id)
    if record is None or record.get("kind") != "approval":
        return {"ok": False, "error": f"결재 건을 찾을 수 없습니다: {approval_id}"}
    return {
        "title": record.get("title"),
        "status": record.get("status"),
        "submitted_on": record.get("submitted_on", ""),
        "history": record.get("history", []),
        **{"days_since_submit": _decorate(record)["days_since_submit"]},
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
