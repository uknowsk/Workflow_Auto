"""오케스트레이터.

흐름은 단순합니다.
  1) 후보 앱들이 제공하는 기능을 전부 모아 LLM 에게 "쓸 수 있는 도구 목록"으로 보여준다
  2) LLM 이 "이 도구를 이렇게 불러줘"라고 하면 그 앱(MCP 서버)을 실제로 호출한다
  3) 결과를 LLM 에게 돌려주고, 더 부를 게 없을 때까지 반복한다
  4) LLM 이 마지막에 만들어 준 문장을 최종 결과물로 저장한다
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.config import get_settings
from app.llm import client as llm
from app.mcp_client import client as mcp
from app.models import App, AppCallLog, AppStatus, AppVisibility

settings = get_settings()

SYSTEM_PROMPT = """너는 사내 업무 자동화 오케스트레이터다.
사용자의 요청을 읽고, 등록된 앱들의 기능을 필요한 만큼 순서대로 호출해서 일을 처리한다.

규칙
- 필요한 정보가 도구로 얻을 수 있는 것이면 추측하지 말고 도구를 호출해라.
- 도구가 없거나 요청을 처리할 수 없으면, 무엇이 부족한지 솔직히 적어라.
- 최종 답은 사용자가 그대로 쓸 수 있는 한국어 결과물로 작성해라.
"""

_SAFE_NAME = re.compile(r"[^a-zA-Z0-9_-]")


@dataclass
class Step:
    """앱 호출 1건의 기록. 화면에 진행상황으로 보여줍니다."""

    app: str
    tool: str
    arguments: dict
    output: str = ""
    error: bool = False

    def as_dict(self) -> dict:
        return {
            "app": self.app,
            "tool": self.tool,
            "arguments": self.arguments,
            "output": self.output[:4000],
            "error": self.error,
        }


@dataclass
class ToolBinding:
    """LLM 이 부르는 함수 이름 <-> 실제 앱/기능 연결."""

    function_name: str
    app: App
    tool_name: str
    description: str
    input_schema: dict


@dataclass
class OrchestrationResult:
    result_text: str = ""
    steps: list[dict] = field(default_factory=list)


def _log_call(
    db: Session,
    app: App,
    tool_name: str,
    user_id: str,
    run_id: str,
    success: bool,
    duration_ms: int,
    error_summary: str = "",
) -> None:
    """앱 호출 1건을 기록합니다. 통계('이달의 앱')와 유지보수에 씁니다.

    통계 기록이 실패해도 사용자의 작업은 계속돼야 하므로 예외를 삼킵니다.
    """
    try:
        db.add(
            AppCallLog(
                app_id=app.id,
                app_slug=app.slug,
                app_name=app.name,
                owner_user_id=app.owner_user_id,
                tool_name=tool_name,
                user_id=user_id,
                run_id=run_id,
                success=success,
                error_summary=error_summary[:500],
                duration_ms=duration_ms,
                period=datetime.now(timezone.utc).strftime("%Y-%m"),
            )
        )
        db.commit()
    except Exception:
        db.rollback()


def pick_apps(
    apps: list[App],
    user_id: str = "",
    card_app_ids: set[str] | None = None,
    request_text: str = "",
) -> list[App]:
    """같은 일을 하는 앱이 여러 개면 하나만 남깁니다.

    왜 필요한가: 예를 들어 사내규정 검색 앱이 공식 앱 A 와 어떤 사용자의
    개인 앱 B 로 두 개 있으면, 오케스트레이터가 둘 다 불러서 서로 다른 답을
    받아 헷갈릴 수 있습니다. 그래서 '역할 태그(capability_tag)'가 같은
    앱끼리는 아래 우선순위로 딱 하나만 씁니다.

      1순위  사용자가 요청문에 앱 이름을 직접 적은 앱
      2순위  사용자가 자기 카드에 넣어 둔 앱
      3순위  사용자 본인이 올린 개인용 앱
      4순위  관리자가 승인한 공식 앱

    태그가 비어 있거나 서로 다르면 경쟁이 아니므로 전부 후보로 둡니다.
    """
    card_app_ids = card_app_ids or set()
    lowered = (request_text or "").lower()

    def rank(app: App) -> int:
        if app.name and app.name.lower() in lowered:
            return 0
        if app.slug and app.slug.lower() in lowered:
            return 0
        if app.id in card_app_ids:
            return 1
        if user_id and app.owner_user_id == user_id:
            return 2
        return 3

    chosen: dict[str, App] = {}
    passthrough: list[App] = []
    for app in apps:
        tag = (app.capability_tag or "").strip()
        if not tag:
            passthrough.append(app)
            continue
        current = chosen.get(tag)
        if current is None or rank(app) < rank(current):
            chosen[tag] = app

    return passthrough + list(chosen.values())


def load_bindings(
    db: Session,
    app_ids: list[str] | None,
    user_id: str = "",
    request_text: str = "",
) -> list[ToolBinding]:
    """후보 앱들의 기능을 모아 LLM 도구 목록으로 만듭니다.

    오케스트레이터가 부를 수 있는 앱은
      - 관리자가 승인한 공식 앱(approved) 전부, 그리고
      - 요청한 본인이 올린 개인용 앱
    입니다. 남이 올린 개인용 앱은 절대 후보에 들어가지 않습니다.
    그다음 pick_apps() 로 역할이 겹치는 앱을 하나로 정리합니다.
    """
    query = db.query(App).filter(App.status == AppStatus.active)
    query = query.filter(
        (App.visibility == AppVisibility.approved) | (App.owner_user_id == user_id)
    )
    if app_ids:
        query = query.filter(App.id.in_(app_ids))

    candidates = pick_apps(
        query.all(),
        user_id=user_id,
        card_app_ids=set(app_ids or []),
        request_text=request_text,
    )

    bindings: list[ToolBinding] = []
    used: set[str] = set()
    for app in candidates:
        for tool in app.tools:
            base = _SAFE_NAME.sub("_", f"{app.slug}__{tool.name}")[:60]
            name = base
            suffix = 1
            while name in used:  # 이름이 겹치면 뒤에 번호를 붙입니다
                name = f"{base[:57]}_{suffix}"
                suffix += 1
            used.add(name)

            description = tool.description or ""
            if app.usage_hint:
                description = f"[{app.name}] {app.usage_hint}\n{description}".strip()
            bindings.append(
                ToolBinding(
                    function_name=name,
                    app=app,
                    tool_name=tool.name,
                    description=description[:1000],
                    input_schema=tool.input_schema or {"type": "object", "properties": {}},
                )
            )
    return bindings


def to_openai_tools(bindings: list[ToolBinding]) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": b.function_name,
                "description": b.description,
                "parameters": b.input_schema or {"type": "object", "properties": {}},
            },
        }
        for b in bindings
    ]


async def run_request(
    db: Session,
    request_text: str,
    app_ids: list[str] | None = None,
    user_id: str = "",
    run_id: str = "",
    on_step: Callable[[list[dict]], None] | None = None,
) -> OrchestrationResult:
    """자연어 요청 1건을 끝까지 처리합니다."""
    bindings = load_bindings(db, app_ids, user_id, request_text)
    by_name = {b.function_name: b for b in bindings}
    tools = to_openai_tools(bindings)

    if not tools:
        return OrchestrationResult(
            result_text=(
                "등록되어 사용할 수 있는 앱이 없습니다. "
                "앱스토어에 앱을 먼저 등록해 주세요."
            )
        )

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": request_text},
    ]
    steps: list[Step] = []

    for _ in range(settings.llm_max_steps):
        reply = llm.chat(messages, tools=tools)

        if not reply["tool_calls"]:
            return OrchestrationResult(
                result_text=reply["content"], steps=[s.as_dict() for s in steps]
            )

        messages.append(llm.assistant_call_message(reply))

        for call in reply["tool_calls"]:
            binding = by_name.get(call["name"])
            if binding is None:
                output, is_error = f"'{call['name']}' 이라는 기능은 없습니다.", True
                step = Step(app="?", tool=call["name"], arguments=call["arguments"])
            else:
                step = Step(
                    app=binding.app.name,
                    tool=binding.tool_name,
                    arguments=call["arguments"],
                )
                started = time.monotonic()
                try:
                    output, is_error = await mcp.call_tool(
                        binding.app.endpoint,
                        binding.tool_name,
                        call["arguments"],
                        headers=binding.app.auth_headers or {},
                        timeout=settings.mcp_timeout,
                    )
                except Exception as exc:  # 앱이 죽어 있어도 전체가 멈추면 안 됩니다
                    output, is_error = f"앱 호출 실패: {exc}", True

                _log_call(
                    db,
                    binding.app,
                    binding.tool_name,
                    user_id=user_id,
                    run_id=run_id,
                    success=not is_error,
                    duration_ms=int((time.monotonic() - started) * 1000),
                    error_summary=output if is_error else "",
                )

            step.output = output
            step.error = is_error
            steps.append(step)
            if on_step:
                on_step([s.as_dict() for s in steps])

            messages.append(llm.tool_result_message(call, output or "(빈 결과)"))

    # 호출 횟수 상한에 걸린 경우: 지금까지 모은 것으로 마무리를 시킵니다.
    messages.append(
        {"role": "user", "content": "여기까지 얻은 결과만으로 최종 결과물을 작성해라."}
    )
    final = llm.chat(messages, tools=None)
    return OrchestrationResult(
        result_text=final["content"], steps=[s.as_dict() for s in steps]
    )
