"""등록된 앱(=MCP 서버)을 호출하는 얇은 클라이언트.

MCP 표준(streamable HTTP)만 씁니다. 그래서 개발자는 자기 앱을 MCP 서버로
감싸기만 하면 되고, 우리 쪽에 앱별 코드를 추가할 필요가 없습니다.
자세한 규약은 docs/WRAPPER_SPEC.md 참고.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


@dataclass
class ToolInfo:
    name: str
    description: str
    input_schema: dict


def _content_to_text(result: Any) -> str:
    """MCP 결과를 사람이 읽을 수 있는 문자열 하나로 눌러 담습니다."""
    chunks: list[str] = []
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        if text is not None:
            chunks.append(text)
            continue
        # 이미지/리소스 등은 요약만 남깁니다.
        chunks.append(f"[{getattr(item, 'type', 'content')}]")

    joined = "\n".join(chunks).strip()
    if joined:
        return joined
    # 텍스트가 없으면 구조화된 결과를 JSON 으로 돌려줍니다.
    if getattr(result, "structuredContent", None):
        return json.dumps(result.structuredContent, ensure_ascii=False, indent=2)
    return ""


async def list_tools(endpoint: str, headers: dict[str, str] | None = None,
                     timeout: float = 60.0) -> list[ToolInfo]:
    """앱이 제공하는 기능 목록을 읽어옵니다. 앱 등록/새로고침 때 호출."""
    async with streamablehttp_client(endpoint, headers=headers or {}, timeout=timeout) as (
        read, write, _,
    ):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            return [
                ToolInfo(
                    name=t.name,
                    description=t.description or "",
                    input_schema=t.inputSchema or {},
                )
                for t in result.tools
            ]


async def call_tool(endpoint: str, tool_name: str, arguments: dict,
                    headers: dict[str, str] | None = None,
                    timeout: float = 60.0) -> tuple[str, bool]:
    """앱의 기능 하나를 실행합니다. (결과텍스트, 오류여부) 를 돌려줍니다."""
    async with streamablehttp_client(endpoint, headers=headers or {}, timeout=timeout) as (
        read, write, _,
    ):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                tool_name,
                arguments or {},
                read_timeout_seconds=timedelta(seconds=timeout),
            )
            return _content_to_text(result), bool(result.isError)
