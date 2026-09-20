"""레시피 실행기.

오케스트레이터(engine.py)와 무엇이 다른가
  engine.py : "무엇을 어떤 순서로 할지"를 LLM 이 매번 새로 정합니다. 똑똑하지만 느립니다.
  recipe.py : 이미 정해진 순서대로 앱을 그대로 부릅니다. LLM 을 거의 안 써서 빠르고,
              같은 입력이면 같은 결과가 나옵니다.

그래서 한 번 잘 돌아간 흐름은 레시피로 저장해 두고 버튼 하나로 재실행합니다.

단계 인자 안에는 {{변수}} 를 쓸 수 있습니다.
  {{회의록}}  실행할 때 사용자가 채워 넣는 값
  {{step1}}   1번째 단계가 돌려준 결과 (앞 단계 결과를 다음 단계에 넘길 때)
  {{today}}   오늘 날짜, {{now}} 지금 시각, {{user_id}} 실행한 사람 사번, {{user_name}} 이름
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.config import get_settings
from app.llm import client as llm
from app.mcp_client import client as mcp
from app.models import App, AppStatus, AppVisibility
from app.orchestrator.engine import OrchestrationResult, Step, _log_call, _log_usage

settings = get_settings()

# {{이름}} 형태를 찾습니다. 한글 변수 이름도 씁니다.
_PLACEHOLDER = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
_STEP_REF = re.compile(r"^step([1-9][0-9]*)$")
# 사용자가 채워 넣을 필요가 없는(시스템이 알아서 넣는) 이름들
BUILTIN_NAMES = {"today", "now", "user_id", "user_name"}

FINAL_PROMPT = """너는 사내 업무 자동화 도우미다.
아래는 정해진 순서대로 앱을 호출해 얻은 결과들이다.
이것만 가지고 사용자가 그대로 쓸 수 있는 한국어 결과물을 작성해라.
없는 내용을 지어내지 마라.
"""


def local_now() -> datetime:
    """사내 표준시 기준 '지금'. (한국이면 UTC+9)"""
    return datetime.now(timezone.utc) + timedelta(
        minutes=settings.scheduler_tz_offset_minutes
    )


def base_context(user_id: str = "", user_name: str = "") -> dict[str, str]:
    now = local_now()
    return {
        "today": now.strftime("%Y-%m-%d"),
        "now": now.strftime("%Y-%m-%d %H:%M"),
        "user_id": user_id,
        # 앱에 따라 담당자를 사번이 아니라 이름으로 들고 있습니다(할 일 앱의 owner 등).
        # 이름을 모르면 사번을 그대로 씁니다.
        "user_name": user_name or user_id,
    }


def fill(value: Any, context: dict[str, str]) -> Any:
    """인자 안의 {{변수}} 를 실제 값으로 바꿉니다. 목록/사전 안까지 들어갑니다.

    모르는 변수는 빈 문자열이 아니라 원래 글자 그대로 둡니다.
    그래야 "어, 이 값이 안 채워졌네"를 결과에서 바로 알아볼 수 있습니다.
    """
    if isinstance(value, str):
        return _PLACEHOLDER.sub(
            lambda m: context.get(m.group(1), m.group(0)), value
        )
    if isinstance(value, list):
        return [fill(item, context) for item in value]
    if isinstance(value, dict):
        return {key: fill(item, context) for key, item in value.items()}
    return value


def find_variables(steps: list[dict], final_instruction: str = "") -> list[str]:
    """실행할 때 사용자가 채워 넣어야 하는 변수 이름 목록.

    {{step1}} 이나 {{today}} 처럼 시스템이 알아서 넣는 값은 빼고 돌려줍니다.
    """
    found: list[str] = []
    texts = [final_instruction]
    for step in steps or []:
        texts.append(str(step.get("arguments", "")))
    for name in _PLACEHOLDER.findall("\n".join(texts)):
        if name in BUILTIN_NAMES or _STEP_REF.match(name) or name in found:
            continue
        found.append(name)
    return found


def _load_app(db: Session, app_id: str, user_id: str) -> App | None:
    """단계가 가리키는 앱을 꺼냅니다. 못 쓰는 앱이면 None.

    레시피를 저장한 뒤에 앱이 지워지거나, 공식 앱이 개인용으로 내려갔을 수
    있으므로 실행할 때마다 다시 확인합니다.
    """
    app = db.get(App, app_id) if app_id else None
    if app is None or app.status != AppStatus.active:
        return None
    if app.visibility != AppVisibility.approved and app.owner_user_id != user_id:
        return None
    return app


def plan_from_steps(db: Session, steps: list[dict], user_id: str) -> tuple[list[dict], bool]:
    """레시피 단계를 '실행 전 확인' 화면에 쓸 계획으로 바꿉니다.

    되돌릴 수 없는 앱(메일 발송 등)이 하나라도 있으면 True 를 같이 돌려줍니다.
    """
    plan: list[dict] = []
    needs_approval = False
    for index, step in enumerate(steps or [], start=1):
        app = _load_app(db, step.get("app_id", ""), user_id)
        confirm = bool(app and app.requires_confirmation)
        needs_approval = needs_approval or confirm
        plan.append(
            {
                "app": app.name if app else step.get("app_name", "(없어진 앱)"),
                "tool": step.get("tool", ""),
                "why": step.get("title", "") or f"{index}번째 단계",
                "requires_confirmation": confirm,
            }
        )
    return plan, needs_approval


async def execute(
    db: Session,
    steps: list[dict],
    final_instruction: str = "",
    form_text: str = "",
    variables: dict[str, str] | None = None,
    user_id: str = "",
    run_id: str = "",
    on_step: Callable[[list[dict]], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> OrchestrationResult:
    """정해진 단계를 위에서부터 차례로 실행합니다.

    한 단계가 실패하면 거기서 멈춥니다. 앞 단계 결과를 받아 쓰는 구조라
    그냥 이어 가면 엉뚱한 내용으로 메일이 나갈 수 있기 때문입니다.

    should_stop 은 "사용자가 멈춤을 눌렀나?"를 묻는 함수입니다. 다음 단계로
    넘어가기 전에 물어봅니다(같은 이유로, 이미 시작한 단계는 끝까지 갑니다).
    """
    context = base_context(user_id)
    context.update({k: str(v) for k, v in (variables or {}).items()})

    records: list[Step] = []
    outputs: list[str] = []

    for index, raw in enumerate(steps or [], start=1):
        if should_stop and should_stop():
            return OrchestrationResult(
                result_text="", steps=[r.as_dict() for r in records]
            )

        app = _load_app(db, raw.get("app_id", ""), user_id)
        tool_name = raw.get("tool", "")
        arguments = fill(raw.get("arguments") or {}, context)

        record = Step(
            app=app.name if app else raw.get("app_name", "(없어진 앱)"),
            tool=tool_name,
            arguments=arguments,
        )

        if app is None:
            record.output = (
                f"'{raw.get('app_name') or raw.get('app_slug')}' 앱을 지금은 쓸 수 없습니다. "
                "삭제됐거나 권한이 바뀌었는지 앱스토어에서 확인해 주세요."
            )
            record.error = True
        else:
            started = time.monotonic()
            try:
                output, is_error = await mcp.call_tool(
                    app.endpoint,
                    tool_name,
                    arguments,
                    headers=app.auth_headers or {},
                    timeout=settings.mcp_timeout,
                )
            except Exception as exc:  # 앱이 죽어 있어도 전체가 멈추면 안 됩니다
                output, is_error = f"앱 호출 실패: {exc}", True

            _log_call(
                db,
                app,
                tool_name,
                user_id=user_id,
                run_id=run_id,
                success=not is_error,
                duration_ms=int((time.monotonic() - started) * 1000),
                error_summary=output if is_error else "",
            )
            record.output, record.error = output, is_error

        records.append(record)
        if on_step:
            on_step([r.as_dict() for r in records])

        if record.error:
            return OrchestrationResult(
                result_text=(
                    f"{index}번째 단계 '{record.app} · {tool_name}' 에서 멈췄습니다.\n"
                    f"{record.output}"
                ),
                steps=[r.as_dict() for r in records],
            )

        outputs.append(record.output)
        context[f"step{index}"] = record.output

    if not records:
        return OrchestrationResult(result_text="레시피에 단계가 없습니다.")

    # 마무리. 지시문이 없으면 LLM 을 부르지 않고 단계 결과를 그대로 이어 붙입니다.
    if not final_instruction.strip():
        joined = "\n\n".join(
            f"[{r.app} · {r.tool}]\n{out}" for r, out in zip(records, outputs)
        )
        return OrchestrationResult(
            result_text=joined, steps=[r.as_dict() for r in records]
        )

    collected = "\n\n".join(
        f"[{index}단계 {r.app} · {r.tool}]\n{out}"
        for index, (r, out) in enumerate(zip(records, outputs), start=1)
    )
    user_message = f"{fill(final_instruction, context)}\n\n--- 단계별 결과 ---\n{collected}"
    if form_text:
        user_message += f"\n\n--- 이 양식에 맞춰 작성해라 ---\n{form_text}"

    reply = llm.chat(
        [
            {"role": "system", "content": FINAL_PROMPT},
            {"role": "user", "content": user_message},
        ],
        tools=None,
    )
    _log_usage(db, reply, user_id, run_id)
    return OrchestrationResult(
        result_text=reply["content"], steps=[r.as_dict() for r in records]
    )
