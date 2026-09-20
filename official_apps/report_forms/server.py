"""보고서 양식 제작 앱 - 수명업무 보고서를 옵션 두 개만 골라 만듭니다.

위에서 "이거 검토해서 보고해" 하고 일이 내려왔을 때, 빈 화면 앞에서 무엇부터
써야 하나 고민하는 시간을 없애는 것이 목적입니다.

고르는 것은 두 가지뿐입니다.
  1) 보고서 종류 - 검토 / 결과 / 출장 / 현황 / 이슈 / 회의결과
  2) 분량        - 1장(핵심만) / 3장(표준) / 상세
그러면 그 조합에 맞는 항목과 작성 안내가 들어간 양식을 워드·엑셀·PPT·HTML 중
고른 형식으로 만들어 줍니다.

초안 작성은 **옵션**입니다. draft=True 로 부르면 지시 내용(context)을 읽고
항목마다 첫 문장까지 써 줍니다. 사내 Gauss 가 없거나 실패하면 빈 양식으로
돌려주므로 앱이 멈추지는 않습니다(결과의 drafted_by 로 구분).

실행:  python -m report_forms.server   ->  http://localhost:9118/mcp
"""
import os
import uuid
from pathlib import Path

from common.store import DATA_DIR, Store, today_iso
from mcp.server.fastmcp import FastMCP

from report_forms import builder, catalog

PORT = int(os.getenv("PORT", "9118"))
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", f"http://localhost:{PORT}").rstrip("/")
OUTPUT_DIR = DATA_DIR / "reports"

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "not-needed")
LLM_MODEL = os.getenv("LLM_MODEL", "gauss")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))

store = Store("report_forms")

mcp = FastMCP(
    "보고서 양식 제작",
    instructions=(
        "수명업무 보고서를 만듭니다. 보고서 종류와 분량을 고르면 그에 맞는 항목과 "
        "작성 안내가 든 양식을 워드·엑셀·PPT·HTML 로 만들어 줍니다. "
        "지시 내용을 같이 주고 draft=True 로 부르면 초안 문장까지 씁니다."
    ),
    host=os.getenv("HOST", "0.0.0.0"),
    port=PORT,
)

_client = None


def _llm():
    global _client
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY, timeout=LLM_TIMEOUT)
    return _client


def _write_draft(report_type: str, title: str, context: str, sections: list[dict]) -> str:
    """항목별 초안을 한 번의 호출로 받아 옵니다. 실패하면 빈 문자열."""
    outline = "\n".join(f"## {s['title']}\n({s['guide']})" for s in sections)
    system = (
        "당신은 한국 대기업의 보고서 작성을 돕는 비서입니다. "
        "사실을 지어내지 말고, 주어진 내용에 없는 숫자나 이름은 (확인 필요) 로 남기세요. "
        "문장은 '~함', '~임' 같은 보고서 어투로 짧게 씁니다."
    )
    user = (
        f"보고서 종류: {report_type}\n제목: {title}\n\n"
        f"[지시 내용 및 참고 자료]\n{context}\n\n"
        "아래 항목 순서와 제목을 그대로 두고, 각 제목 아래에 내용을 쓰세요. "
        "괄호 안의 안내문은 결과에 넣지 마세요.\n\n" + outline
    )
    response = _llm().chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.3,
    )
    return (response.choices[0].message.content or "").strip()


def _split_draft(text: str, sections: list[dict]) -> dict[str, str]:
    """'## 제목' 으로 나뉜 답을 항목별로 갈라 담습니다.

    모델이 제목을 조금 다르게 적는 일이 잦아서, 정확히 같지 않아도 이름이 겹치면
    같은 항목으로 봅니다. 그래도 못 찾으면 나온 순서대로 채웁니다.
    """
    blocks: list[tuple[str, list[str]]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            blocks.append((stripped.lstrip("#").strip(), []))
        elif blocks:
            blocks[-1][1].append(line)

    filled: dict[str, str] = {}
    leftovers: list[tuple[str, str]] = []
    for heading, lines in blocks:
        body = "\n".join(lines).strip()
        if not body:
            continue
        match = next(
            (s for s in sections if s["title"] == heading or s["title"] in heading or heading in s["title"]),
            None,
        )
        if match and match["key"] not in filled:
            filled[match["key"]] = body
        else:
            leftovers.append((heading, body))

    if not filled and leftovers:  # 제목을 하나도 못 맞춘 경우: 순서대로
        for section, (_, body) in zip(sections, leftovers):
            filled[section["key"]] = body
    return filled


def _make_doc(record: dict) -> dict:
    """저장해 둔 기록을 파일 생성기가 먹는 모양으로 바꿉니다."""
    return {
        "title": record["title"],
        "report_type": record["report_type"],
        "length": record["length"],
        "header": [(label, record.get("header", {}).get(key, "")) for label, key in catalog.HEADER_FIELDS],
        "sections": record["sections"],
    }


def _render(record: dict, file_format: str) -> dict:
    stem = f"{record['id']}_{file_format}"
    made = builder.build(_make_doc(record), file_format, OUTPUT_DIR, stem)
    if "error" in made:
        return {"ok": False, "error": made["error"]}
    answer = {"ok": True, "report_id": record["id"], "format": file_format}
    if made.get("document"):
        answer["document"] = made["document"]
    if made.get("path"):
        answer["download_url"] = f"{PUBLIC_BASE_URL}/files/{made['path'].name}"
    return answer


@mcp.tool()
def list_report_types() -> dict:
    """만들 수 있는 보고서 종류와 분량 선택지를 알려 줍니다.

    사용자에게 "무엇을 고를 수 있는지" 보여 줄 때 먼저 부르세요.
    """
    return {
        "types": [
            {
                "type": name,
                "when": info["when"],
                "example": info["example"],
                "sections_by_length": {
                    length: [s["title"] for s in catalog.sections_for(name, length)]
                    for length in catalog.LENGTHS
                },
            }
            for name, info in catalog.REPORT_TYPES.items()
        ],
        "lengths": [{"length": k, "hint": v["hint"]} for k, v in catalog.LENGTHS.items()],
        "formats": ["word", "excel", "ppt", "html"],
    }


@mcp.tool()
def recommend_options(instruction: str) -> dict:
    """받은 지시 내용을 보고 어떤 종류·분량이 맞을지 추천합니다.

    LLM 없이 글자만 보고 고르므로 항상 즉시 답합니다. 사용자가 다르게 고르면
    그 선택이 우선입니다.

    Args:
        instruction: 위에서 내려온 지시 내용. 예) "A설비 도입 타당성 검토해서 보고"
    """
    text = (instruction or "").replace(" ", "")
    report_type = ""
    for name, words in catalog.KEYWORDS:
        if any(word.replace(" ", "") in text for word in words):
            report_type = name
            break
    report_type = report_type or "검토보고"

    if any(word in text for word in ("임원", "사장", "부사장", "간단히", "한장", "1장", "요약")):
        length = "1장"
    elif any(word in text for word in ("상세", "자세", "전체", "근거", "심층")):
        length = "상세"
    else:
        length = catalog.DEFAULT_LENGTH

    return {
        "report_type": report_type,
        "length": length,
        "why": f"지시 내용에서 '{report_type}' 에 해당하는 말이 보여 골랐습니다.",
        "sections": [s["title"] for s in catalog.sections_for(report_type, length)],
    }


@mcp.tool()
def build_report(
    report_type: str,
    title: str = "",
    length: str = "",
    output_format: str = "word",
    author: str = "",
    dept: str = "",
    ordered_by: str = "",
    ordered_on: str = "",
    due_on: str = "",
    draft: bool = False,
    context: str = "",
    user_id: str = "",
) -> dict:
    """고른 옵션대로 보고서 양식(필요하면 초안까지)을 만들어 파일로 돌려줍니다.

    Args:
        report_type: 보고서 종류. 검토보고/결과보고/출장보고/현황보고/이슈보고/회의결과보고
        title: 보고서 제목. 비우면 "(종류)"로 자동
        length: 분량. 1장 / 3장 / 상세 (기본 3장)
        output_format: word, excel, ppt, html 중 하나 (기본 word)
        author: 작성자 이름
        dept: 소속 부서
        ordered_by: 지시자. 예) 김 상무
        ordered_on: 지시받은 날짜. 예) 2026-09-18
        due_on: 제출 기한
        draft: True 면 context 를 읽어 초안 문장까지 씁니다 (사내 LLM 사용)
        context: 지시 내용과 참고 자료. draft=True 일 때만 씁니다
        user_id: 사번. 예) E1001
    """
    resolved_type = catalog.resolve_type(report_type)
    if not resolved_type:
        return {
            "ok": False,
            "error": f"모르는 보고서 종류입니다: {report_type}",
            "choices": list(catalog.REPORT_TYPES),
        }
    resolved_length = catalog.resolve_length(length)
    file_format = builder.resolve_format(output_format)
    if not file_format:
        return {
            "ok": False,
            "error": f"모르는 형식입니다: {output_format}",
            "choices": ["word", "excel", "ppt", "html"],
        }

    sections = [dict(s, body="") for s in catalog.sections_for(resolved_type, resolved_length)]
    drafted_by = "none"
    draft_error = ""
    if draft:
        if not (context or "").strip():
            draft_error = "초안을 쓰려면 지시 내용(context)이 필요합니다. 빈 양식으로 만들었습니다."
        else:
            try:
                answer = _write_draft(resolved_type, title or resolved_type, context, sections)
                bodies = _split_draft(answer, sections)
                if bodies:
                    for section in sections:
                        section["body"] = bodies.get(section["key"], "")
                    drafted_by = "llm"
                else:
                    draft_error = "초안을 항목별로 나누지 못해 빈 양식으로 만들었습니다."
            except Exception as exc:  # LLM 이 없거나 죽어도 양식은 나와야 합니다
                draft_error = f"초안 생성 실패({type(exc).__name__}). 빈 양식으로 만들었습니다."

    record = store.put(
        "report",
        {
            "title": title or resolved_type,
            "report_type": resolved_type,
            "length": resolved_length,
            "header": {
                "reported_on": today_iso(),
                "author": author,
                "dept": dept,
                "ordered_by": ordered_by,
                "ordered_on": ordered_on,
                "due_on": due_on,
            },
            "sections": sections,
            "drafted_by": drafted_by,
            "context": context if draft else "",
        },
        user_id=user_id,
    )

    result = _render(record, file_format)
    if not result.get("ok"):
        return result
    result.update(
        {
            "report_type": resolved_type,
            "length": resolved_length,
            "sections": [s["title"] for s in sections],
            "drafted_by": drafted_by,
            "note": (
                "항목과 작성 안내가 들어 있는 양식입니다. 안내 문구는 내용을 채우면서 지우세요."
                if drafted_by == "none"
                else "초안이 들어 있습니다. 숫자와 이름은 반드시 확인하세요."
            ),
        }
    )
    if draft_error:
        result["draft_error"] = draft_error
    return result


@mcp.tool()
def export_report(report_id: str, output_format: str) -> dict:
    """이미 만든 보고서를 다른 형식으로 다시 뽑습니다. (워드로 만든 걸 PPT 로 등)

    Args:
        report_id: 만들 때 받은 보고서 id
        output_format: word, excel, ppt, html 중 하나
    """
    record = store.get(report_id)
    if record is None or record.get("kind") != "report":
        return {"ok": False, "error": f"보고서를 찾을 수 없습니다: {report_id}"}
    file_format = builder.resolve_format(output_format)
    if not file_format:
        return {"ok": False, "error": f"모르는 형식입니다: {output_format}"}
    return _render(record, file_format)


@mcp.tool()
def fill_section(report_id: str, section_title: str, body: str) -> dict:
    """만들어 둔 보고서의 한 항목을 사람이 쓴 내용으로 채웁니다.

    채운 뒤 export_report 를 부르면 그 내용이 들어간 파일이 나옵니다.

    Args:
        report_id: 보고서 id
        section_title: 항목 이름. 예) 검토 결론
        body: 그 항목에 넣을 내용
    """
    record = store.get(report_id)
    if record is None or record.get("kind") != "report":
        return {"ok": False, "error": f"보고서를 찾을 수 없습니다: {report_id}"}
    sections = [dict(s) for s in record["sections"]]
    target = next(
        (s for s in sections if s["title"] == section_title or section_title in s["title"]), None
    )
    if target is None:
        return {
            "ok": False,
            "error": f"그런 항목이 없습니다: {section_title}",
            "choices": [s["title"] for s in sections],
        }
    target["body"] = body
    store.update(report_id, sections=sections)
    return {
        "ok": True,
        "report_id": report_id,
        "filled": target["title"],
        "empty_sections": [s["title"] for s in sections if not (s.get("body") or "").strip()],
    }


@mcp.tool()
def list_reports(user_id: str = "", limit: int = 10) -> dict:
    """내가 만든 보고서 목록을 최근 것부터 돌려줍니다.

    Args:
        user_id: 사번. 비우면 전체
        limit: 몇 개까지 볼지
    """
    records = store.list("report", user_id=user_id)
    records.reverse()
    return {
        "count": len(records),
        "reports": [
            {
                "report_id": r["id"],
                "title": r["title"],
                "report_type": r["report_type"],
                "length": r["length"],
                "drafted_by": r.get("drafted_by", "none"),
                "made_on": r["created_at"],
            }
            for r in records[: max(1, limit)]
        ],
    }


@mcp.tool()
def get_report(report_id: str) -> dict:
    """보고서 하나의 항목과 채워진 내용을 전부 돌려줍니다.

    Args:
        report_id: 보고서 id
    """
    record = store.get(report_id)
    if record is None or record.get("kind") != "report":
        return {"ok": False, "error": f"보고서를 찾을 수 없습니다: {report_id}"}
    return {
        "ok": True,
        "report_id": record["id"],
        "title": record["title"],
        "report_type": record["report_type"],
        "length": record["length"],
        "header": record.get("header", {}),
        "sections": [
            {"title": s["title"], "guide": s["guide"], "body": s.get("body", "")}
            for s in record["sections"]
        ],
        "drafted_by": record.get("drafted_by", "none"),
    }


@mcp.custom_route("/files/{filename}", methods=["GET"])
async def download_report(request):
    """만든 보고서 파일을 내려받는 주소.

    MCP 로는 파일을 그대로 실어 보내기 어려워서, 파일은 여기 두고 주소만 알려 줍니다.
    """
    from starlette.responses import FileResponse, JSONResponse

    name = Path(request.path_params["filename"]).name  # 경로가 섞여 들어오는 것 방지
    file = OUTPUT_DIR / name
    if not file.is_file():
        return JSONResponse({"error": "파일을 찾을 수 없습니다."}, status_code=404)
    return FileResponse(file, filename=name)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
