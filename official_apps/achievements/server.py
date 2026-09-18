"""업적 정리 앱 - 고과 때 낼 근거자료를 평소에 모아 둡니다.

연말에 "내가 올해 뭐 했더라" 하고 기억을 쥐어짜지 않도록, 한 일을 그때그때
한 줄씩 쌓아 두고 나중에 기간을 잘라 정리해 줍니다.

기록이 들어오는 길은 둘입니다.
  1. 사용자가 직접 추가 (add_achievement)
  2. 오케스트레이터가 다른 앱에서 모아 온 기록을 한 번에 넣기 (import_achievements)
     예) 할 일 앱의 완료 목록, 메일 앱의 발송 내역, 산출물 초안 목록
     아직 그 앱들이 없으면 이 기능은 비어 있는 채로 기다립니다.

실행:  python -m achievements.server   ->  http://localhost:9112/mcp
"""
import os

from mcp.server.fastmcp import FastMCP

from common.dates import parse_date
from common.store import Store, today_iso

store = Store("achievements")

mcp = FastMCP(
    "업적 정리 (고과 근거자료)",
    instructions=(
        "사용자가 수행한 업무를 기간별로 모아 고과 평가에 제출할 수 있는 형태로 정리합니다."
    ),
    host=os.getenv("HOST", "0.0.0.0"),
    port=int(os.getenv("PORT", "9112")),
)

# 업적을 나누는 기본 분류. 회사 고과 항목이 다르면 이 목록만 바꾸면 됩니다.
CATEGORIES = ["개발", "개선", "협업", "교육", "기타"]


def _normalize(item: dict, source: str) -> dict:
    """어떤 앱에서 온 기록이든 같은 모양으로 맞춥니다."""
    return {
        "title": str(item.get("title") or item.get("name") or item.get("subject") or "제목 없음"),
        "detail": str(item.get("detail") or item.get("description") or item.get("body") or ""),
        "category": str(item.get("category") or "기타"),
        "date": str(item.get("date") or item.get("completed_on") or item.get("created_at") or today_iso())[:10],
        "impact": str(item.get("impact") or item.get("result") or ""),
        "source": source,
    }


@mcp.tool()
def add_achievement(
    user_id: str,
    title: str,
    detail: str = "",
    category: str = "기타",
    date: str = "",
    impact: str = "",
) -> dict:
    """내가 한 일을 업적으로 한 건 기록합니다.

    Args:
        user_id: 사번. 예) E1001
        title: 한 일. 예) 차세대 MES 설계서 작성
        detail: 구체적인 내용
        category: 분류. 개발/개선/협업/교육/기타
        date: 수행한 날짜. 비우면 오늘. 예) 2026-09-18
        impact: 결과나 효과. 예) 처리시간 30% 단축
    """
    return store.put(
        "achievement",
        {
            "title": title,
            "detail": detail,
            "category": category if category in CATEGORIES else "기타",
            "date": (date or today_iso())[:10],
            "impact": impact,
            "source": "직접 입력",
        },
        user_id=user_id,
    )


@mcp.tool()
def import_achievements(user_id: str, items: list[dict], source: str = "다른 앱") -> dict:
    """다른 앱에서 가져온 업무 기록들을 업적으로 한 번에 넣습니다.

    완료한 할 일, 보낸 메일, 작성한 산출물처럼 이미 다른 앱에 남아 있는 기록을
    오케스트레이터가 조회해서 이 기능으로 넘기면 업적 목록에 쌓입니다.

    Args:
        user_id: 사번. 예) E1001
        items: 기록 목록. 각 항목은 title, detail, date, category, impact 를 가질 수 있습니다.
        source: 어디서 가져왔는지. 예) 할 일 앱
    """
    saved = [store.put("achievement", _normalize(item, source), user_id=user_id) for item in items or []]
    return {"ok": True, "added": len(saved), "source": source}


@mcp.tool()
def list_achievements(
    user_id: str,
    start_date: str = "",
    end_date: str = "",
    category: str = "",
) -> dict:
    """기간과 분류로 내 업적 기록을 찾아 돌려줍니다.

    Args:
        user_id: 사번. 예) E1001
        start_date: 시작일. 비우면 처음부터. 예) 2026-01-01
        end_date: 종료일. 비우면 오늘까지. 예) 2026-12-31
        category: 분류로 걸러낼 때. 개발/개선/협업/교육/기타
    """
    records = store.list("achievement", user_id=user_id, category=category)
    start = parse_date(start_date, fallback=parse_date("1900-01-01"))
    end = parse_date(end_date)
    picked = [r for r in records if start <= parse_date(r.get("date", "")) <= end]
    picked.sort(key=lambda r: r.get("date", ""))
    return {"count": len(picked), "period": f"{start} ~ {end}", "achievements": picked}


@mcp.tool()
def update_achievement(
    achievement_id: str,
    title: str = "",
    detail: str = "",
    category: str = "",
    impact: str = "",
    date: str = "",
) -> dict:
    """기록해 둔 업적의 내용을 고칩니다. 비운 항목은 그대로 둡니다.

    Args:
        achievement_id: 업적 id
        title: 새 제목
        detail: 새 내용
        category: 새 분류
        impact: 새 성과
        date: 새 날짜. 예) 2026-09-18
    """
    fields = {k: v for k, v in
              {"title": title, "detail": detail, "category": category, "impact": impact, "date": date}.items()
              if v}
    updated = store.update(achievement_id, **fields)
    if updated is None:
        return {"ok": False, "error": f"업적을 찾을 수 없습니다: {achievement_id}"}
    return {"ok": True, "achievement": updated}


@mcp.tool()
def delete_achievement(achievement_id: str) -> dict:
    """잘못 들어간 업적 기록 하나를 지웁니다.

    Args:
        achievement_id: 업적 id
    """
    return {"ok": store.delete(achievement_id), "achievement_id": achievement_id}


@mcp.tool()
def summarize_period(
    user_id: str,
    start_date: str,
    end_date: str = "",
    author_name: str = "",
) -> str:
    """기간 동안의 업적을 고과 제출용 정리 문서로 만들어 줍니다.

    분류별로 묶고, 성과가 적힌 항목을 앞에 둡니다. 그대로 복사해서 쓰거나
    필요한 부분만 다듬어 쓰면 됩니다.

    Args:
        user_id: 사번. 예) E1001
        start_date: 시작일. 예) 2026-01-01
        end_date: 종료일. 비우면 오늘까지. 예) 2026-06-30
        author_name: 문서에 적을 이름. 예) 김로아
    """
    found = list_achievements(user_id, start_date, end_date)
    records = found["achievements"]
    if not records:
        return f"{found['period']} 기간에 기록된 업적이 없습니다. 업적을 먼저 등록해 주세요."

    lines = [
        "[업무 수행 실적 정리]",
        f"대상 기간: {found['period']}",
        f"작성자: {author_name or user_id}",
        f"총 {len(records)}건",
        "",
    ]
    for category in CATEGORIES:
        group = [r for r in records if r.get("category") == category]
        if not group:
            continue
        group.sort(key=lambda r: (not r.get("impact"), r.get("date", "")))
        lines.append(f"■ {category} ({len(group)}건)")
        for record in group:
            line = f"  - [{record.get('date', '')}] {record.get('title', '')}"
            if record.get("impact"):
                line += f"  → 성과: {record['impact']}"
            lines.append(line)
            if record.get("detail"):
                lines.append(f"      {record['detail']}")
        lines.append("")

    highlights = [r for r in records if r.get("impact")]
    lines.append(f"■ 대표 성과 ({len(highlights)}건)")
    for record in highlights[:5]:
        lines.append(f"  - {record.get('title', '')}: {record['impact']}")
    if not highlights:
        lines.append("  - (성과가 적힌 업적이 없습니다. impact 항목을 채우면 여기 올라옵니다)")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
