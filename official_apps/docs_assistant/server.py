"""문서 요약/번역 앱 - 긴 사양서나 영문 자료를 한 장으로 줄이고, 한↔영 번역을 합니다.

사내 Gauss 같은 OpenAI 호환 LLM 에 그대로 연결합니다. 플랫폼과 같은 환경변수
(LLM_BASE_URL, LLM_API_KEY, LLM_MODEL)를 쓰므로 .env 값을 그대로 물려받습니다.

긴 문서는 한 번에 넣으면 잘리므로, 토막으로 나눠 각각 요약한 뒤 그 요약들을
다시 한 번 합칩니다. 사람이 두꺼운 보고서를 읽을 때 장별로 메모하고 마지막에
합치는 것과 같습니다.

실행:  python -m docs_assistant.server   ->  http://localhost:9107/mcp
"""
import os

from mcp.server.fastmcp import FastMCP
from openai import OpenAI

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "not-needed")
LLM_MODEL = os.getenv("LLM_MODEL", "gauss")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))
# 한 번에 LLM 에 넣을 글자 수. 모델이 작으면 줄이세요.
CHUNK_CHARS = int(os.getenv("DOC_CHUNK_CHARS", "6000"))

mcp = FastMCP(
    "문서 요약/번역",
    instructions="긴 문서를 요약하거나 한국어↔영어로 번역합니다.",
    host=os.getenv("HOST", "0.0.0.0"),
    port=int(os.getenv("PORT", "9107")),
)

_client: OpenAI | None = None


def _llm() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY, timeout=LLM_TIMEOUT)
    return _client


def _ask(system: str, user: str) -> str:
    response = _llm().chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.2,
    )
    return (response.choices[0].message.content or "").strip()


def _chunks(text: str) -> list[str]:
    """긴 글을 문단 경계에서 토막냅니다. 문장이 중간에서 잘리지 않게."""
    paragraphs = text.split("\n")
    blocks, current = [], ""
    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 1 > CHUNK_CHARS and current:
            blocks.append(current)
            current = paragraph
        else:
            current = f"{current}\n{paragraph}" if current else paragraph
    if current.strip():
        blocks.append(current)
    return blocks or [text]


def _map_reduce(text: str, system: str, instruction: str, combine: str) -> str:
    """토막마다 처리한 뒤 결과를 한 번 더 합칩니다."""
    blocks = _chunks(text)
    if len(blocks) == 1:
        return _ask(system, f"{instruction}\n\n---\n{blocks[0]}")
    partials = [
        _ask(system, f"{instruction}\n\n(전체 {len(blocks)}토막 중 {i + 1}번째)\n---\n{block}")
        for i, block in enumerate(blocks)
    ]
    return _ask(system, f"{combine}\n\n---\n" + "\n\n".join(partials))


@mcp.tool()
def summarize_document(text: str, max_bullets: int = 5, focus: str = "") -> dict:
    """긴 문서를 핵심만 뽑아 불릿으로 요약합니다.

    Args:
        text: 요약할 문서 본문
        max_bullets: 불릿 최대 개수. 기본 5
        focus: 특히 알고 싶은 것. 예) 일정과 비용 위주로
    """
    if not text.strip():
        return {"ok": False, "error": "요약할 본문이 비어 있습니다."}

    focus_line = f"특히 다음 관점에 집중해라: {focus}\n" if focus else ""
    system = "너는 사내 문서를 정확하게 요약하는 비서다. 문서에 없는 내용을 지어내지 마라."
    try:
        summary = _map_reduce(
            text,
            system,
            f"{focus_line}아래 문서를 한국어 불릿 {max_bullets}개 이하로 요약해라. "
            "숫자와 날짜, 담당자는 그대로 살려라.",
            f"{focus_line}아래는 같은 문서를 토막내어 요약한 것들이다. "
            f"중복을 합쳐 한국어 불릿 {max_bullets}개 이하의 최종 요약으로 만들어라.",
        )
    except Exception as exc:
        return {"ok": False, "error": f"LLM 호출에 실패했습니다: {exc}", "llm": LLM_BASE_URL}
    return {"ok": True, "source_chars": len(text), "summary": summary}


@mcp.tool()
def one_page_summary(text: str, audience: str = "임원") -> dict:
    """긴 자료를 보고용 한 장 요약으로 만듭니다. 배경, 핵심, 쟁점, 건의 순서입니다.

    Args:
        text: 요약할 문서 본문
        audience: 누가 읽을지. 예) 임원, 팀원, 협력사
    """
    if not text.strip():
        return {"ok": False, "error": "요약할 본문이 비어 있습니다."}

    system = "너는 사내 보고서를 한 장으로 압축하는 비서다. 문서에 없는 내용을 지어내지 마라."
    layout = (
        f"읽는 사람은 {audience} 이다. 아래 문서를 한국어 한 장 요약으로 만들어라.\n"
        "형식:\n1. 배경 (2줄)\n2. 핵심 내용 (불릿 3~5개)\n"
        "3. 쟁점 / 위험 (불릿 2~3개)\n4. 건의 사항 (2줄)"
    )
    try:
        page = _map_reduce(
            text,
            system,
            layout,
            f"아래는 같은 문서의 토막 요약들이다. 이것을 합쳐 위 형식대로 한 장 요약을 만들어라.\n{layout}",
        )
    except Exception as exc:
        return {"ok": False, "error": f"LLM 호출에 실패했습니다: {exc}", "llm": LLM_BASE_URL}
    return {"ok": True, "audience": audience, "one_pager": page}


@mcp.tool()
def translate_document(text: str, target_language: str = "영어", tone: str = "업무용") -> dict:
    """문서를 다른 언어로 번역합니다. 한국어↔영어를 주로 씁니다.

    Args:
        text: 번역할 본문
        target_language: 어떤 언어로. 예) 영어, 한국어
        tone: 말투. 예) 업무용, 격식체, 편한 말투
    """
    if not text.strip():
        return {"ok": False, "error": "번역할 본문이 비어 있습니다."}

    system = (
        "너는 사내 문서 번역가다. 뜻을 바꾸지 말고, 고유명사와 숫자는 그대로 두고, "
        "원문의 줄바꿈과 목록 구조를 유지해라. 번역문만 출력해라."
    )
    instruction = f"아래 글을 {target_language}로 {tone} 말투로 번역해라."
    try:
        blocks = _chunks(text)
        translated = "\n".join(_ask(system, f"{instruction}\n\n---\n{block}") for block in blocks)
    except Exception as exc:
        return {"ok": False, "error": f"LLM 호출에 실패했습니다: {exc}", "llm": LLM_BASE_URL}
    return {"ok": True, "target_language": target_language, "translation": translated}


@mcp.tool()
def llm_status() -> dict:
    """이 앱이 어떤 LLM 에 연결되어 있는지 알려줍니다. 문제가 생겼을 때 확인용입니다."""
    try:
        answer = _ask("한 단어로만 답해라.", "연결 확인. '정상' 이라고만 답해라.")
        return {"ok": True, "base_url": LLM_BASE_URL, "model": LLM_MODEL, "reply": answer[:50]}
    except Exception as exc:
        return {"ok": False, "base_url": LLM_BASE_URL, "model": LLM_MODEL, "error": str(exc)}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
