"""[기존 앱 - 건드리지 않습니다]

비개발자가 바이브 코딩으로 만든 사내 웹앱이라고 가정한 예시입니다.
MCP 를 전혀 모르고, 그냥 자기 방식대로 만든 HTTP API 입니다.
Workflow Auto 에 붙일 때 이 파일은 한 줄도 고치지 않습니다.
대신 옆에 있는 mcp_adapter/ 가 이 앱을 대신 호출해 줍니다.

실행:  uvicorn app:app --port 8100
"""
from datetime import date

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="인사/보고서 도우미 (기존 앱)")

EMPLOYEES = {
    "E1001": {"name": "김로아", "team": "플랫폼개발팀", "position": "책임", "manager": "박부장"},
    "E1002": {"name": "이하늘", "team": "플랫폼개발팀", "position": "선임", "manager": "박부장"},
    "E2001": {"name": "최바다", "team": "품질보증팀", "position": "책임", "manager": "정부장"},
}


@app.get("/employee/{employee_id}")
def employee(employee_id: str):
    record = EMPLOYEES.get(employee_id.strip().upper())
    if record is None:
        return {"found": False, "message": f"사번 {employee_id} 을(를) 찾을 수 없습니다."}
    return {"found": True, "employee_id": employee_id.strip().upper(), **record}


@app.get("/search")
def search(team: str):
    matched = [
        {"employee_id": eid, **info}
        for eid, info in EMPLOYEES.items()
        if team.strip() in info["team"]
    ]
    return {"count": len(matched), "employees": matched}


class ReportIn(BaseModel):
    author_name: str
    team: str
    done_this_week: list[str]
    plan_next_week: list[str]
    issues: str = ""


@app.post("/report/weekly")
def weekly_report(payload: ReportIn):
    def bullets(items: list[str]) -> str:
        return "\n".join(f"  - {item}" for item in items) or "  - (없음)"

    text = (
        f"[주간업무보고]\n"
        f"작성일: {date.today().isoformat()}\n"
        f"소속: {payload.team}\n"
        f"작성자: {payload.author_name}\n\n"
        f"1. 금주 실적\n{bullets(payload.done_this_week)}\n\n"
        f"2. 차주 계획\n{bullets(payload.plan_next_week)}\n\n"
        f"3. 이슈 및 요청사항\n  {payload.issues or '(없음)'}\n"
    )
    return {"document": text}
