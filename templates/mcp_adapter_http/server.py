"""[템플릿] 이미 있는 "웹앱/HTTP API" 를 MCP 로 감싸는 얇은 어댑터.

내 앱은 한 줄도 고치지 않습니다. 이 파일만 옆에 두고 실행하면,
Workflow Auto 오케스트레이터가 내 앱을 부를 수 있게 됩니다.

쓰는 법
  1) 아래 TODO 부분만 내 앱에 맞게 고칩니다 (함수 1개 = 기능 1개).
  2) pip install -r requirements.txt
  3) python server.py        ->  http://localhost:9001/mcp
  4) 이 주소를 Workflow Auto 앱스토어에 등록합니다.

직접 고치기 어렵다면 docs/WRAPPER_PROMPT.md 의 프롬프트를
Claude / Codex / Cline 에 그대로 붙여넣으세요. 대신 채워 줍니다.

주의: 파일 맨 위에 `from __future__ import annotations` 를 넣지 마세요.
      MCP 가 함수의 인자 타입을 읽지 못하게 됩니다.
"""
import os

import httpx
from mcp.server.fastmcp import FastMCP

# ── 내 앱 주소. 환경변수로 빼 두면 집/회사에서 값만 바꿔 끼울 수 있습니다. ──
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8100")
TIMEOUT = float(os.getenv("APP_TIMEOUT", "30"))

mcp = FastMCP(
    # TODO: 내 앱 이름과 한 줄 설명으로 바꾸세요.
    "내 앱 이름",
    instructions="이 앱이 무엇을 해 주는지 한 문장으로 적으세요.",
    host=os.getenv("HOST", "0.0.0.0"),
    port=int(os.getenv("PORT", "9001")),
)


def _client() -> httpx.Client:
    # 사내 인증이 필요하면 headers 에 넣으세요. 값은 환경변수로 받는 것을 권장합니다.
    headers = {}
    token = os.getenv("APP_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.Client(base_url=APP_BASE_URL, timeout=TIMEOUT, headers=headers)


# ──────────────────────────────────────────────────────────────────────
# TODO: 여기부터 내 앱의 기능을 하나씩 함수로 만듭니다.
#
# 규칙 3가지만 지키면 됩니다.
#   1) 함수 위에 @mcp.tool() 을 붙인다
#   2) 인자마다 타입을 적는다 (str, int, list[str] ...)
#   3) docstring 첫 줄에 "이 기능이 뭘 하는지"를 한국어로 적는다
#      -> 오케스트레이터는 이 설명만 보고 언제 이 기능을 쓸지 판단합니다.
# ──────────────────────────────────────────────────────────────────────


@mcp.tool()
def example_get(item_id: str) -> dict:
    """(예시) 내 앱에서 항목 하나를 조회합니다. 설명을 실제 기능에 맞게 바꾸세요.

    Args:
        item_id: 조회할 항목의 ID
    """
    with _client() as client:
        response = client.get(f"/items/{item_id}")
        response.raise_for_status()
        return response.json()


@mcp.tool()
def example_create(title: str, body: str = "") -> dict:
    """(예시) 내 앱에 항목을 하나 만듭니다. 설명을 실제 기능에 맞게 바꾸세요.

    Args:
        title: 제목
        body: 내용 (없으면 비워 두세요)
    """
    with _client() as client:
        response = client.post("/items", json={"title": title, "body": body})
        response.raise_for_status()
        return response.json()


if __name__ == "__main__":
    # streamable-http = Workflow Auto 가 호출하는 MCP 표준 전송 방식
    mcp.run(transport="streamable-http")
