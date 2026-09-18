"""LLM 어댑터 (콘센트 어댑터 역할).

OpenAI 호환 형식만 알면 되므로, 사내 Gauss / vLLM / Ollama 무엇이든
LLM_BASE_URL, LLM_API_KEY, LLM_MODEL 세 값만 바꿔 끼우면 됩니다.

LLM_TOOL_MODE
  native : LLM 의 tools 파라미터(함수 호출)를 그대로 사용 - 권장
  json   : 함수 호출을 지원하지 않는 모델용 우회. "JSON 으로만 답하라"고 시켜
           같은 모양의 호출 계획을 받아냅니다.
"""
from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from app.config import get_settings

settings = get_settings()

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            timeout=settings.llm_timeout,
        )
    return _client


# --------------------------------------------------------------------------
# json 모드용: 함수 호출을 흉내내는 프롬프트
# --------------------------------------------------------------------------
_JSON_MODE_RULES = """
너는 도구를 쓸 수 있다. 반드시 아래 두 가지 형태 중 하나의 JSON 하나만 출력해라.
설명, 인사말, 코드펜스를 붙이지 마라.

도구를 부를 때:
{"action": "call_tool", "tool": "<도구이름>", "arguments": {<인자>}}

더 부를 도구가 없고 최종 답을 낼 때:
{"action": "final", "answer": "<사용자에게 보여줄 최종 결과물>"}

사용 가능한 도구 목록(JSON Schema):
%s
"""

_JSON_BLOCK = re.compile(r"\{.*\}", re.S)


def _extract_json(text: str) -> dict | None:
    match = _JSON_BLOCK.search(text or "")
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def chat(messages: list[dict], tools: list[dict] | None = None) -> dict:
    """LLM 한 번 호출.

    반환값은 tool_mode 와 무관하게 항상 같은 모양입니다.
      {"tool_calls": [{"id", "name", "arguments"}], "content": "..."}
    tool_calls 가 비어 있으면 content 가 최종 답입니다.
    """
    client = get_client()

    if tools and settings.llm_tool_mode == "native":
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
        message = response.choices[0].message
        calls = []
        for call in message.tool_calls or []:
            try:
                arguments = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}
            calls.append({"id": call.id, "name": call.function.name, "arguments": arguments})
        return {"tool_calls": calls, "content": message.content or ""}

    # --- json 모드 (함수 호출 미지원 모델) ---
    prepared = list(messages)
    if tools:
        schema_text = json.dumps(
            [t["function"] for t in tools], ensure_ascii=False, indent=2
        )
        prepared = [
            {"role": "system", "content": _JSON_MODE_RULES % schema_text}
        ] + prepared

    response = client.chat.completions.create(
        model=settings.llm_model, messages=prepared
    )
    raw = response.choices[0].message.content or ""
    parsed = _extract_json(raw)

    if parsed and parsed.get("action") == "call_tool" and parsed.get("tool"):
        return {
            "tool_calls": [
                {
                    "id": "json-mode-call",
                    "name": parsed["tool"],
                    "arguments": parsed.get("arguments") or {},
                }
            ],
            "content": "",
        }
    if parsed and parsed.get("action") == "final":
        return {"tool_calls": [], "content": str(parsed.get("answer", ""))}
    # JSON 을 못 알아들으면 그냥 본문을 최종 답으로 취급합니다.
    return {"tool_calls": [], "content": raw}


def tool_result_message(call: dict[str, Any], output: str) -> dict:
    """도구 실행 결과를 다음 LLM 호출에 넣을 메시지로 만듭니다."""
    if settings.llm_tool_mode == "native":
        return {"role": "tool", "tool_call_id": call["id"], "content": output}
    return {"role": "user", "content": f"[도구 {call['name']} 실행 결과]\n{output}"}


def assistant_call_message(result: dict) -> dict:
    """LLM 이 방금 낸 도구 호출을 대화 기록에 되돌려 넣습니다."""
    if settings.llm_tool_mode == "native":
        return {
            "role": "assistant",
            "content": result.get("content") or None,
            "tool_calls": [
                {
                    "id": c["id"],
                    "type": "function",
                    "function": {
                        "name": c["name"],
                        "arguments": json.dumps(c["arguments"], ensure_ascii=False),
                    },
                }
                for c in result["tool_calls"]
            ],
        }
    calls = result["tool_calls"]
    return {
        "role": "assistant",
        "content": json.dumps(
            {"action": "call_tool", "tool": calls[0]["name"], "arguments": calls[0]["arguments"]},
            ensure_ascii=False,
        ),
    }
