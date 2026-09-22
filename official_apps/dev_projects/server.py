"""개발 프로젝트 앱 - 내 프로젝트와 단계별 산출물을 관리합니다.

하는 일 세 가지
  1. 내가 속한 개발 프로젝트를 등록하고 목록으로 봅니다.
  2. 지금 단계에서 무엇을 내야 하는지(산출물 목록) 알려 줍니다.
  3. 양식을 꺼내 오케스트레이터가 모아 온 내용으로 채워 산출물 초안을 만듭니다.

양식은 두 군데서 옵니다.
  - 이 앱이 기본으로 들고 있는 양식 (forms/ 폴더, FORMS_DIR 로 교체 가능)
  - 플랫폼의 양식 저장소 (WORKFLOW_API_BASE 를 설정하면 읽어 옵니다)

마크다운·텍스트 양식은 채운 내용을 글로 돌려주고, 엑셀·워드·PPT 양식은 서식을
그대로 둔 채 값만 채워 파일로 만들어 내려받기 주소를 돌려줍니다.

실행:  python -m dev_projects.server   ->  http://localhost:9111/mcp
"""
import os
import re
import uuid
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

from common import office
from common.dates import days_between, parse_date
from common.store import DATA_DIR, Store, today_iso

FORMS_DIR = Path(os.getenv("FORMS_DIR", Path(__file__).parent / "forms"))
# 플랫폼 양식 저장소를 같이 쓰고 싶을 때만 채웁니다. 비어 있으면 기본 양식만 씁니다.
WORKFLOW_API_BASE = os.getenv("WORKFLOW_API_BASE", "").rstrip("/")
WORKFLOW_API_TOKEN = os.getenv("WORKFLOW_API_TOKEN", "")
WORKFLOW_API_USER = os.getenv("WORKFLOW_API_USER", "")
# 채운 엑셀·워드 파일을 두는 곳과, 사용자가 내려받을 때 쓰는 주소
OUTPUT_DIR = DATA_DIR / "filled"
PORT = int(os.getenv("PORT", "9111"))
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", f"http://localhost:{PORT}").rstrip("/")

store = Store("dev_projects")

mcp = FastMCP(
    "개발 프로젝트 관리",
    instructions=(
        "내가 속한 개발 프로젝트를 등록/조회하고, 단계별로 내야 하는 산출물을 알려 주고, "
        "양식에 내용을 채워 산출물 초안을 만듭니다."
    ),
    host=os.getenv("HOST", "0.0.0.0"),
    port=PORT,
)

# 단계별로 보통 무엇을 내는지. 회사 표준이 다르면 이 표만 고치면 됩니다.
STAGE_DELIVERABLES = {
    "기획": ["사업계획서", "요구사항 수집 결과"],
    "분석": ["요구사항정의서", "업무흐름도"],
    "설계": ["시스템설계서", "화면설계서", "DB설계서"],
    "구현": ["단위시험결과서", "형상 등록 내역"],
    "시험": ["통합시험계획서", "시험결과서"],
    "이행": ["이행계획서", "완료보고서", "운영 인수인계서"],
}
STAGES = list(STAGE_DELIVERABLES)

# "설계완료 2026-03-31" 처럼 이름과 날짜가 한 덩어리로 들어옵니다.
_MILESTONE = re.compile(r"(\d{4}[-/.]?\d{1,2}[-/.]?\d{1,2})")
# 산출물은 대괄호로 덧붙입니다. 예) 설계완료 2026-03-31 [시스템설계서, 화면설계서]
_DELIVERABLES = re.compile(r"\[([^\]]*)\]")


def parse_milestones(text: str) -> list[dict]:
    """'설계완료 2026-03-31, PP 2026-05-20' 을 [{name, date, deliverables}, ...] 로 바꿉니다.

    마일스톤에서 내야 하는 산출물은 대괄호로 덧붙일 수 있습니다.
        설계완료 2026-03-31 [시스템설계서, 화면설계서]
    안 적으면 이름에서 단계(기획/분석/설계/구현/시험/이행)를 찾아 그 단계의
    산출물을 씁니다. 날짜가 없는 토막은 버립니다(시간축에 찍을 수 없으니까).
    """
    milestones: list[dict] = []
    for chunk in re.split(r"[,\n;](?![^\[]*\])", text or ""):
        chunk = chunk.strip()
        if not chunk:
            continue
        found = _MILESTONE.search(chunk)
        if not found:
            continue
        deliverables: list[str] = []
        bracket = _DELIVERABLES.search(chunk)
        if bracket:
            deliverables = [d.strip() for d in bracket.group(1).split(",") if d.strip()]
            chunk = chunk.replace(bracket.group(0), " ")
        name = chunk.replace(found.group(1), "").strip(" -:·\t")
        name = name or "마일스톤"
        milestones.append(
            {
                "name": name,
                "date": parse_date(found.group(1)).isoformat(),
                "deliverables": deliverables or _deliverables_for(name),
            }
        )
    milestones.sort(key=lambda m: m["date"])
    return milestones


def _deliverables_for(name: str) -> list[str]:
    """마일스톤 이름에 단계 이름이 들어 있으면 그 단계의 산출물을 씁니다.

    예) '설계완료' -> 설계 단계의 산출물. 못 찾으면 빈 목록.
    """
    for stage, items in STAGE_DELIVERABLES.items():
        if stage in name:
            return list(items)
    return []


def _decorate(project: dict) -> dict:
    """화면이 그대로 그릴 수 있도록 날짜 계산을 붙여 줍니다.

    시간축은 시작일 ~ RTS(개발완료) 사이이고, 오늘이 그 사이 몇 % 지점인지를
    같이 넣어 줍니다. RTS 가 없으면 목표 완료일, 그것도 없으면 마지막 마일스톤을 씁니다.
    """
    project = dict(project)
    milestones = list(project.get("milestones") or [])

    end = project.get("rts_date") or project.get("due_date") or ""
    if not end and milestones:
        end = milestones[-1]["date"]
    # RTS 는 시간축의 끝이므로 마일스톤 줄에도 같이 보여 줍니다(중복은 피합니다).
    if project.get("rts_date") and not any(
        m["date"] == project["rts_date"] for m in milestones
    ):
        milestones.append(
            {"name": "RTS (개발완료)", "date": project["rts_date"], "deliverables": []}
        )
    milestones.sort(key=lambda m: m["date"])

    # 이 프로젝트로 이미 만들어 둔 산출물 초안 이름. 마일스톤별 완료 표시에 씁니다.
    made = {
        d.get("form_name", "")
        for d in (store.list("draft", project_id=project.get("id", "")) if project.get("id") else [])
    }

    start = project.get("start_date") or (milestones[0]["date"] if milestones else today_iso())
    span = days_between(start, end) if end else 0
    passed = days_between(start)

    for m in milestones:
        m["days_left"] = -days_between(m["date"])
        m["passed"] = m["days_left"] < 0
        m["percent"] = round(days_between(start, m["date"]) / span * 100, 1) if span > 0 else 100.0
        items = list(m.get("deliverables") or [])
        # 산출물은 이름이 같은 초안이 있으면 "냈다"로 봅니다.
        m["deliverables"] = [{"name": item, "done": item in made} for item in items]
        m["done_count"] = sum(1 for d in m["deliverables"] if d["done"])
        # 마일스톤이 끝났다고 보려면 날짜가 지났고 산출물도 다 나와야 합니다.
        m["done"] = bool(items) and m["done_count"] == len(items)

    project["milestones"] = milestones
    project["days_left"] = -days_between(end) if end else None
    project["next_deliverables"] = STAGE_DELIVERABLES.get(project.get("stage", ""), [])
    project["timeline"] = {
        "start": start,
        "end": end,
        "today": today_iso(),
        # 오늘이 시간축 어디쯤인지. 0 이면 시작일, 100 이면 RTS 당일입니다.
        "percent": max(0.0, min(100.0, round(passed / span * 100, 1))) if span > 0 else 100.0,
    }
    return project


_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
TEXT_SUFFIXES = {".md", ".txt", ".csv"}


def _front_matter(path: Path) -> dict:
    """마크다운 양식 맨 위의 ---  --- 안에 적어 둔 이름/단계/설명을 읽습니다."""
    meta = {"name": path.stem, "stage": "", "description": ""}
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return meta
    match = _FRONT_MATTER.match(path.read_text(encoding="utf-8"))
    if match:
        for line in match.group(1).splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                meta[key.strip()] = value.strip()
    return meta


def _form_body(path: Path) -> str:
    """마크다운 양식의 본문(머리말 제외)."""
    raw = path.read_text(encoding="utf-8")
    match = _FRONT_MATTER.match(raw)
    return (raw[match.end():] if match else raw).strip()


def _builtin_forms() -> list[dict]:
    """이 앱이 기본으로 들고 있는 양식 목록."""
    if not FORMS_DIR.is_dir():
        return []
    forms = []
    for file in sorted(FORMS_DIR.iterdir()):
        if file.suffix.lower() not in office.SUPPORTED:
            continue
        forms.append(
            {
                "form_key": file.stem,
                "file_type": file.suffix.lstrip("."),
                "source": "기본 양식",
                "path": file,
                **_front_matter(file),
            }
        )
    return forms


def _platform_client() -> httpx.Client | None:
    """플랫폼 양식 저장소에 물어볼 준비가 됐으면 클라이언트를, 아니면 None."""
    if not WORKFLOW_API_BASE:
        return None
    headers = {}
    if WORKFLOW_API_TOKEN:
        headers["Authorization"] = f"Bearer {WORKFLOW_API_TOKEN}"
    if WORKFLOW_API_USER:
        headers["X-User-Id"] = WORKFLOW_API_USER
    return httpx.Client(base_url=WORKFLOW_API_BASE, headers=headers, timeout=30)


def _platform_forms() -> tuple[list[dict], str]:
    """플랫폼 양식 저장소의 양식 목록. (목록, 문제가 있으면 안내문)"""
    client = _platform_client()
    if client is None:
        return [], ""
    try:
        with client:
            response = client.get("/api/forms")
            response.raise_for_status()
            items = response.json()
    except Exception as exc:
        return [], f"양식 저장소를 읽지 못했습니다: {exc}"

    return [
        {
            "form_key": f"platform:{item['id']}",
            "name": item.get("name", ""),
            "description": item.get("description", ""),
            "stage": item.get("category", ""),
            "file_type": Path(item.get("filename", "")).suffix.lstrip("."),
            "source": "양식 저장소",
        }
        for item in items
    ], ""


def _download_platform_form(form_id: str) -> Path:
    """양식 저장소의 양식 파일을 잠깐 받아 둡니다."""
    client = _platform_client()
    if client is None:
        raise RuntimeError(
            "양식 저장소 주소(WORKFLOW_API_BASE)가 설정되지 않아 이 양식은 쓸 수 없습니다."
        )
    cache = DATA_DIR / "form_cache"
    cache.mkdir(parents=True, exist_ok=True)
    with client:
        response = client.get(f"/api/forms/{form_id}/download")
        response.raise_for_status()
        disposition = response.headers.get("content-disposition", "")
        match = re.search(r'filename="?([^"]+)"?', disposition)
        filename = match.group(1) if match else f"{form_id}.md"
        target = cache / f"{form_id}_{Path(filename).name}"
        target.write_bytes(response.content)
    return target


def _resolve_form(form_key: str) -> dict:
    """양식 키를 실제 파일로 바꿉니다. 못 찾으면 error 를 담아 돌려줍니다."""
    if form_key.startswith("platform:"):
        try:
            file = _download_platform_form(form_key.split(":", 1)[1])
        except Exception as exc:
            return {"error": f"양식 저장소에서 양식을 받지 못했습니다: {exc}"}
        return {"form_key": form_key, "name": file.name, "path": file,
                "file_type": file.suffix.lstrip("."), "source": "양식 저장소"}

    for form in _builtin_forms():
        if form_key in (form["form_key"], form["name"]):
            return form
    return {"error": f"양식을 찾을 수 없습니다: {form_key}",
            "available": [f["form_key"] for f in _builtin_forms()]}


@mcp.tool()
def register_project(
    user_id: str,
    name: str,
    model: str = "",
    role: str = "",
    stage: str = "기획",
    description: str = "",
    start_date: str = "",
    rts_date: str = "",
    due_date: str = "",
    milestones: str = "",
) -> dict:
    """내가 속한 개발 프로젝트를 등록합니다.

    Args:
        user_id: 사번. 예) E1001
        name: 프로젝트 이름
        model: 모델명. 예) SM-X100
        role: 이 프로젝트에서 내 역할. 예) 설계 담당
        stage: 현재 단계. 기획/분석/설계/구현/시험/이행 중 하나
        description: 프로젝트 한 줄 설명
        start_date: 시작일. 예) 2026-01-05
        rts_date: RTS(개발완료) 목표일. 예) 2026-06-30
        due_date: 목표 완료일. 비우면 RTS 날짜를 씁니다.
        milestones: 주요 마일스톤. "이름 날짜" 를 쉼표로 이어서. 예) 설계완료 2026-03-31, PP 2026-05-20
    """
    project = store.put(
        "project",
        {
            "name": name,
            "model": model,
            "role": role,
            "stage": stage if stage in STAGE_DELIVERABLES else "기획",
            "description": description,
            "start_date": start_date or today_iso(),
            "rts_date": rts_date,
            "due_date": due_date or rts_date,
            "milestones": parse_milestones(milestones),
            "status": "진행중",
        },
        user_id=user_id,
    )
    return _decorate(project)


@mcp.tool()
def list_my_projects(user_id: str, include_finished: bool = False) -> dict:
    """내가 등록한 개발 프로젝트 목록을 돌려줍니다.

    프로젝트마다 모델명, 현재 단계, RTS(개발완료) 날짜, 주요 마일스톤, 그리고
    시작일부터 RTS 까지의 시간축에서 오늘이 어디쯤인지를 같이 알려 줍니다.

    Args:
        user_id: 사번. 예) E1001
        include_finished: 완료된 프로젝트도 포함할지
    """
    projects = store.list("project", user_id=user_id)
    if not include_finished:
        projects = [p for p in projects if p.get("status") != "완료"]
    rows = [_decorate(project) for project in projects]
    # 개발완료가 코앞인 것부터 봅니다. 날짜가 없는 것은 뒤로.
    rows.sort(key=lambda r: (r["days_left"] is None, r["days_left"]))
    return {"count": len(rows), "projects": rows}


@mcp.tool()
def set_milestones(project_id: str, milestones: str) -> dict:
    """프로젝트의 주요 마일스톤을 통째로 새로 적습니다.

    Args:
        project_id: 프로젝트 id
        milestones: "이름 날짜" 를 쉼표로 이어서. 예) 설계완료 2026-03-31, PP 2026-05-20, RTS 2026-06-30
    """
    parsed = parse_milestones(milestones)
    if not parsed:
        return {
            "ok": False,
            "error": "마일스톤을 읽지 못했습니다. '설계완료 2026-03-31, PP 2026-05-20' 처럼 적어 주세요.",
        }
    updated = store.update(project_id, milestones=parsed)
    if updated is None:
        return {"ok": False, "error": f"프로젝트를 찾을 수 없습니다: {project_id}"}
    return {"ok": True, "project": _decorate(updated)}


@mcp.tool()
def update_project(
    project_id: str,
    stage: str = "",
    status: str = "",
    model: str = "",
    rts_date: str = "",
    due_date: str = "",
    note: str = "",
) -> dict:
    """프로젝트의 단계나 상태, 기한을 바꿉니다.

    Args:
        project_id: 프로젝트 id
        stage: 새 단계. 기획/분석/설계/구현/시험/이행
        status: 진행중 / 보류 / 완료
        model: 모델명. 예) SM-X100
        rts_date: 새 RTS(개발완료) 목표일. 예) 2026-07-31
        due_date: 새 목표 완료일. 예) 2026-07-31
        note: 메모
    """
    fields = {}
    if stage:
        if stage not in STAGE_DELIVERABLES:
            return {"ok": False, "error": f"단계는 {', '.join(STAGES)} 중 하나여야 합니다."}
        fields["stage"] = stage
    if status:
        fields["status"] = status
    if model:
        fields["model"] = model
    if rts_date:
        fields["rts_date"] = rts_date
        if not due_date:
            fields["due_date"] = rts_date
    if due_date:
        fields["due_date"] = due_date
    if note:
        fields["note"] = note

    updated = store.update(project_id, **fields)
    if updated is None:
        return {"ok": False, "error": f"프로젝트를 찾을 수 없습니다: {project_id}"}
    return {"ok": True, "project": _decorate(updated)}


@mcp.tool()
def list_stage_deliverables(stage: str = "") -> dict:
    """개발 단계별로 작성해야 하는 산출물 목록을 알려줍니다.

    Args:
        stage: 궁금한 단계. 비우면 전체 단계를 돌려줍니다. 예) 설계
    """
    if stage:
        if stage not in STAGE_DELIVERABLES:
            return {"ok": False, "error": f"단계는 {', '.join(STAGES)} 중 하나여야 합니다."}
        return {"stage": stage, "deliverables": STAGE_DELIVERABLES[stage]}
    return {"stages": STAGE_DELIVERABLES}


@mcp.tool()
def project_checklist(project_id: str) -> dict:
    """프로젝트 하나를 보고, 지금 단계에서 내야 할 산출물과 이미 만든 초안을 대조해 줍니다.

    Args:
        project_id: 프로젝트 id
    """
    project = store.get(project_id)
    if project is None or project.get("kind") != "project":
        return {"ok": False, "error": f"프로젝트를 찾을 수 없습니다: {project_id}"}

    drafts = store.list("draft", project_id=project_id)
    made = {d.get("form_name", "") for d in drafts}
    required = STAGE_DELIVERABLES.get(project.get("stage", ""), [])
    return {
        "project": project.get("name"),
        "stage": project.get("stage"),
        "required": required,
        "done": [item for item in required if item in made],
        "todo": [item for item in required if item not in made],
        "drafts": [{"draft_id": d["id"], "form": d.get("form_name"), "made_on": d["created_at"]} for d in drafts],
    }


@mcp.tool()
def list_forms(stage: str = "") -> dict:
    """산출물을 작성할 때 쓸 수 있는 양식 목록을 돌려줍니다.

    이 앱이 기본으로 들고 있는 양식과, 플랫폼 양식 저장소에 올라온 양식을 함께 봅니다.
    마크다운·텍스트는 물론 엑셀·워드·PPT 양식도 값을 채울 수 있습니다.

    Args:
        stage: 특정 단계의 양식만 보고 싶을 때. 예) 분석
    """
    forms = [
        {k: v for k, v in form.items() if k != "path"}
        for form in _builtin_forms()
        if not stage or form.get("stage") == stage
    ]
    platform, note = _platform_forms()
    forms.extend(f for f in platform if not stage or f.get("stage") == stage)

    result = {"count": len(forms), "forms": forms}
    if note:
        result["note"] = note
    return result


@mcp.tool()
def get_form(form_key: str) -> dict:
    """양식 하나를 열어 채워야 하는 항목 목록을 알려줍니다.

    텍스트 양식이면 본문도 같이 돌려줍니다. 엑셀·워드·PPT 양식은 파일이라
    항목 목록만 돌려주고, 채우기는 fill_form 이 합니다.

    Args:
        form_key: 양식 키 또는 이름. 예) requirements, weekly_report, platform:<양식id>
    """
    form = _resolve_form(form_key)
    if "error" in form:
        return {"ok": False, **form}

    file = form["path"]
    info = {k: v for k, v in form.items() if k != "path"}
    info["fields"] = office.find_fields(file)
    if file.suffix.lower() in TEXT_SUFFIXES:
        info["body"] = _form_body(file)
    return info


@mcp.tool()
def fill_form(
    values: dict,
    form_key: str = "",
    form_text: str = "",
    project_id: str = "",
    user_id: str = "",
) -> dict:
    """양식에 내용을 채워 산출물 초안을 만들고 보관합니다.

    - 텍스트 양식이면 채운 문서를 글로 돌려줍니다.
    - 엑셀·워드·PPT 양식이면 서식을 그대로 둔 채 값만 채운 파일을 만들고,
      내려받기 주소(download_url)를 돌려줍니다.
    채우지 못한 항목은 missing 에 알려 주므로 보완해서 다시 부르면 됩니다.

    Args:
        values: 항목 이름과 내용. 예) {"project_name": "차세대 MES", "author": "김로아"}
        form_key: 쓸 양식의 키. 예) requirements 또는 platform:<양식id>
        form_text: 양식 본문을 직접 넘길 때. {{항목}} 자리에 값이 들어갑니다.
        project_id: 이 산출물이 속한 프로젝트 id (있으면 목록에서 같이 보입니다)
        user_id: 사번. 예) E1001
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if form_text.strip():
        source = OUTPUT_DIR / f"inline_{today_iso()}.md"
        source.write_text(form_text, encoding="utf-8")
        form_name, file_type = "직접 넘긴 양식", "md"
    else:
        form = _resolve_form(form_key)
        if "error" in form:
            return {"ok": False, **form}
        source = form["path"]
        form_name = form.get("name") or form.get("form_key", "")
        file_type = source.suffix.lstrip(".")
        if source.suffix.lower() in TEXT_SUFFIXES:
            # 양식 맨 위 설명(--- --- 부분)은 결과물에 들어가면 안 되니 떼고 채웁니다.
            stripped = OUTPUT_DIR / f"body_{uuid.uuid4().hex[:8]}{source.suffix}"
            stripped.write_text(_form_body(source), encoding="utf-8")
            source = stripped

    values = dict(values or {})
    values.setdefault("written_on", today_iso())

    target = OUTPUT_DIR / f"{uuid.uuid4().hex[:8]}_{source.name}"
    try:
        result = office.fill_file(source, target, values)
    except Exception as exc:
        return {"ok": False, "error": f"양식을 채우지 못했습니다: {exc}"}

    document = ""
    if target.suffix.lower() in TEXT_SUFFIXES:
        document = target.read_text(encoding="utf-8")

    draft = store.put(
        "draft",
        {
            "form_key": form_key,
            "form_name": form_name,
            "file_type": file_type,
            "project_id": project_id,
            "filename": target.name,
            "document": document,
            "missing": result["missing"],
        },
        user_id=user_id,
    )
    answer = {
        "ok": True,
        "draft_id": draft["id"],
        "form": form_name,
        "filled": result["filled"],
        "missing": result["missing"],
    }
    if document:
        answer["document"] = document
    else:
        answer["download_url"] = f"{PUBLIC_BASE_URL}/files/{target.name}"
        answer["note"] = "서식을 그대로 둔 채 값만 채운 파일입니다. 주소를 눌러 내려받으세요."
    return answer


@mcp.tool()
def list_drafts(user_id: str, project_id: str = "") -> dict:
    """내가 만든 산출물 초안 목록을 돌려줍니다.

    Args:
        user_id: 사번. 예) E1001
        project_id: 특정 프로젝트 것만 보고 싶을 때
    """
    drafts = store.list("draft", user_id=user_id, project_id=project_id)
    return {
        "count": len(drafts),
        "drafts": [
            {
                "draft_id": d["id"],
                "form": d.get("form_name"),
                "project_id": d.get("project_id", ""),
                "missing": d.get("missing", []),
                "made_on": d["created_at"],
            }
            for d in drafts
        ],
    }


@mcp.tool()
def get_draft(draft_id: str) -> dict:
    """저장해 둔 산출물 초안의 전체 내용을 돌려줍니다.

    Args:
        draft_id: 초안 id
    """
    draft = store.get(draft_id)
    if draft is None or draft.get("kind") != "draft":
        return {"ok": False, "error": f"초안을 찾을 수 없습니다: {draft_id}"}
    return draft


@mcp.custom_route("/files/{filename}", methods=["GET"])
async def download_filled(request):
    """채워 만든 엑셀·워드 파일을 내려받는 주소.

    MCP 는 글을 주고받는 통로라서 파일을 그대로 실어 보내기 어렵습니다.
    그래서 파일은 여기에 두고 주소만 알려 줍니다.
    """
    from starlette.responses import FileResponse, JSONResponse

    name = Path(request.path_params["filename"]).name  # 경로가 섞여 들어오는 것 방지
    file = OUTPUT_DIR / name
    if not file.is_file():
        return JSONResponse({"error": "파일을 찾을 수 없습니다."}, status_code=404)
    return FileResponse(file, filename=name)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
