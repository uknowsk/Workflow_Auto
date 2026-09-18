"""[예시] 옆에 있는 legacy_app 을 MCP 로 감싼 어댑터.

templates/mcp_adapter_http/server.py 를 복사해서 TODO 만 채운 결과물입니다.
legacy_app 의 코드는 한 줄도 고치지 않았습니다.

실행:  python server.py   ->  http://localhost:9001/mcp
"""
import os

import httpx
from mcp.server.fastmcp import FastMCP

APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8100")
TIMEOUT = float(os.getenv("APP_TIMEOUT", "30"))

mcp = FastMCP(
    "사내 인사/보고서 도우미",
    instructions="사번으로 직원 정보를 찾고, 주간보고 양식을 채워 줍니다.",
    host=os.getenv("HOST", "0.0.0.0"),
    port=int(os.getenv("PORT", "9001")),
)


def _client() -> httpx.Client:
    headers = {}
    token = os.getenv("APP_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.Client(base_url=APP_BASE_URL, timeout=TIMEOUT, headers=headers)


@mcp.tool()
def find_employee(employee_id: str) -> dict:
    """사번으로 직원의 이름, 소속팀, 직급, 상위 관리자를 조회합니다.

    Args:
        employee_id: 사번. 예) E1001
    """
    with _client() as client:
        response = client.get(f"/employee/{employee_id}")
        response.raise_for_status()
        return response.json()


@mcp.tool()
def search_employees_by_team(team: str) -> dict:
    """팀 이름으로 소속 직원들을 찾습니다.

    Args:
        team: 팀 이름 일부. 예) 플랫폼
    """
    with _client() as client:
        response = client.get("/search", params={"team": team})
        response.raise_for_status()
        return response.json()


@mcp.tool()
def fill_weekly_report(
    author_name: str,
    team: str,
    done_this_week: list[str],
    plan_next_week: list[str],
    issues: str = "",
) -> str:
    """주간보고 양식에 내용을 채워 완성된 문서를 돌려줍니다.

    Args:
        author_name: 작성자 이름
        team: 소속 팀
        done_this_week: 이번 주에 한 일 목록
        plan_next_week: 다음 주 계획 목록
        issues: 이슈 및 요청사항 (없으면 비워 두세요)
    """
    with _client() as client:
        response = client.post(
            "/report/weekly",
            json={
                "author_name": author_name,
                "team": team,
                "done_this_week": done_this_week,
                "plan_next_week": plan_next_week,
                "issues": issues,
            },
        )
        response.raise_for_status()
        return response.json()["document"]


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
