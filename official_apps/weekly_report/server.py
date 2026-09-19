"""주간보고 자동 생성 앱 - 이번 주 기록을 모아 보고서 초안을 만듭니다.

example_app 의 주간보고 기능을 실제로 쓸 수 있게 넓힌 공식 앱입니다.
달라진 점은 세 가지입니다.
  - 만든 보고서를 저장해 두고 나중에 다시 꺼내 볼 수 있습니다.
  - 지난주에 적은 '차주 계획'을 이번 주 실적 초안으로 끌어옵니다.
  - 다른 앱에서 모아 온 기록(완료한 할 일, 보낸 메일 등)을 그대로 넣을 수 있습니다.

실행:  python -m weekly_report.server   ->  http://localhost:9113/mcp
"""
import os

from mcp.server.fastmcp import FastMCP

from common.dates import parse_date, week_range
from common.store import Store, today_iso

store = Store("weekly_report")

mcp = FastMCP(
    "주간보고 자동 생성",
    instructions="이번 주에 한 일과 다음 주 계획을 모아 주간업무보고 초안을 만들고 보관합니다.",
    host=os.getenv("HOST", "0.0.0.0"),
    port=int(os.getenv("PORT", "9113")),
)


def _bullets(items: list) -> str:
    cleaned = [str(item).strip() for item in (items or []) if str(item).strip()]
    return "\n".join(f"  - {item}" for item in cleaned) or "  - (없음)"


def _render(data: dict) -> str:
    return (
        "[주간업무보고]\n"
        f"보고 주간: {data.get('week_label', '')}\n"
        f"소속: {data.get('team', '')}\n"
        f"작성자: {data.get('author_name', '')}\n"
        f"작성일: {data.get('written_on', today_iso())}\n\n"
        f"1. 금주 실적\n{_bullets(data.get('done_this_week', []))}\n\n"
        f"2. 차주 계획\n{_bullets(data.get('plan_next_week', []))}\n\n"
        f"3. 이슈 및 요청사항\n  {data.get('issues') or '(없음)'}\n"
    )


@mcp.tool()
def draft_weekly_report(
    user_id: str,
    author_name: str,
    team: str,
    done_this_week: list[str],
    plan_next_week: list[str],
    issues: str = "",
    week_of: str = "",
) -> dict:
    """이번 주 주간업무보고 초안을 만들어 돌려주고 보관합니다.

    Args:
        user_id: 사번. 예) E1001
        author_name: 작성자 이름. 예) 김로아
        team: 소속 팀. 예) 플랫폼개발팀
        done_this_week: 이번 주에 한 일 목록
        plan_next_week: 다음 주에 할 일 목록
        issues: 이슈 및 요청사항. 없으면 비워 두세요
        week_of: 보고 주간에 속한 아무 날짜. 비우면 이번 주. 예) 2026-09-14
    """
    monday, friday = week_range(week_of)
    data = {
        "author_name": author_name,
        "team": team,
        "done_this_week": [str(x) for x in done_this_week or []],
        "plan_next_week": [str(x) for x in plan_next_week or []],
        "issues": issues,
        "week_label": f"{monday} ~ {friday}",
        "week_start": str(monday),
        "written_on": today_iso(),
    }
    document = _render(data)
    saved = store.put("report", {**data, "document": document}, user_id=user_id)
    return {"report_id": saved["id"], "week": data["week_label"], "document": document}


@mcp.tool()
def collect_records(user_id: str, records: list[dict], week_of: str = "") -> dict:
    """다른 앱에서 모아 온 기록을 주간보고용 '한 일' 문장으로 다듬어 돌려줍니다.

    완료한 할 일, 보낸 메일, 작성한 산출물처럼 이미 다른 앱에 남아 있는 기록을
    오케스트레이터가 조회해서 여기에 넘기면, 보고서에 바로 넣을 수 있는 문장이 됩니다.

    Args:
        user_id: 사번. 예) E1001
        records: 기록 목록. 각 항목은 title, detail, date 를 가질 수 있습니다.
        week_of: 보고 주간에 속한 아무 날짜. 비우면 이번 주
    """
    monday, friday = week_range(week_of)
    lines = []
    for record in records or []:
        title = str(record.get("title") or record.get("name") or "").strip()
        if not title:
            continue
        when = str(record.get("date") or record.get("completed_on") or "")[:10]
        if when and not (str(monday) <= when <= str(friday)):
            continue
        detail = str(record.get("detail") or record.get("result") or "").strip()
        lines.append(f"{title}{f' ({detail})' if detail else ''}")
    return {"week": f"{monday} ~ {friday}", "count": len(lines), "done_this_week": lines}


@mcp.tool()
def carry_over_plan(user_id: str, week_of: str = "") -> dict:
    """지난주 보고서에 적은 '차주 계획'을 이번 주 실적 초안으로 꺼내 옵니다.

    Args:
        user_id: 사번. 예) E1001
        week_of: 이번 주에 속한 아무 날짜. 비우면 오늘 기준
    """
    monday, _ = week_range(week_of)
    reports = store.list("report", user_id=user_id)
    earlier = [r for r in reports if r.get("week_start", "") < str(monday)]
    if not earlier:
        return {"found": False, "message": "지난주 보고서가 없습니다. 이번 주 내용을 직접 적어 주세요."}
    last = sorted(earlier, key=lambda r: r.get("week_start", ""))[-1]
    return {
        "found": True,
        "last_week": last.get("week_label", ""),
        "suggested_done_this_week": last.get("plan_next_week", []),
        "last_issues": last.get("issues", ""),
    }


@mcp.tool()
def list_reports(user_id: str, limit: int = 10) -> dict:
    """내가 만든 주간보고 목록을 최근 것부터 돌려줍니다.

    Args:
        user_id: 사번. 예) E1001
        limit: 몇 개까지 볼지. 기본 10
    """
    reports = sorted(store.list("report", user_id=user_id), key=lambda r: r.get("week_start", ""), reverse=True)
    return {
        "count": len(reports),
        "reports": [
            {"report_id": r["id"], "week": r.get("week_label", ""), "team": r.get("team", "")}
            for r in reports[: max(1, limit)]
        ],
    }


@mcp.tool()
def get_report(report_id: str) -> dict:
    """보관해 둔 주간보고의 전체 내용을 돌려줍니다.

    Args:
        report_id: 보고서 id
    """
    report = store.get(report_id)
    if report is None or report.get("kind") != "report":
        return {"ok": False, "error": f"보고서를 찾을 수 없습니다: {report_id}"}
    return report


@mcp.tool()
def monthly_digest(user_id: str, month: str = "") -> str:
    """한 달치 주간보고를 모아 월간 요약 초안을 만듭니다.

    Args:
        user_id: 사번. 예) E1001
        month: 대상 월. 예) 2026-09. 비우면 이번 달
    """
    target = (month or today_iso())[:7]
    reports = [r for r in store.list("report", user_id=user_id) if r.get("week_start", "")[:7] == target]
    if not reports:
        return f"{target} 에 저장된 주간보고가 없습니다."

    reports.sort(key=lambda r: r.get("week_start", ""))
    lines = [f"[{target} 월간 요약]", f"주간보고 {len(reports)}건을 모았습니다.", ""]
    for report in reports:
        lines.append(f"■ {report.get('week_label', '')}")
        lines.append(_bullets(report.get("done_this_week", [])))
        if report.get("issues"):
            lines.append(f"  · 이슈: {report['issues']}")
        lines.append("")
    last = reports[-1]
    lines.append("■ 다음 달로 넘어가는 계획")
    lines.append(_bullets(last.get("plan_next_week", [])))
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
