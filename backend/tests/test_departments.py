"""부서 공통 앱·카드가 "같은 부서에게만" 보이는지 확인합니다.

여기가 조용히 틀리면 남의 부서 앱과 카드가 전사에 보입니다. 그래서
  - 부서원에게는 보이고
  - 부서 밖 사람에게는 목록에도, 상세에도, 오케스트레이터 후보에도 안 보이고
  - 만들고 고치는 것은 부서 담당자만
이 세 가지를 모두 확인합니다.

환경(파일 하나짜리 sqlite + 관리자 E9999)은 tests/conftest.py 에서 정합니다.
"""
import pytest

ADMIN = {"X-User-Id": "E9999"}
MANAGER = {"X-User-Id": "D1001"}   # SW개발팀 담당자
MEMBER = {"X-User-Id": "D1002"}    # SW개발팀 부서원
OUTSIDER = {"X-User-Id": "D2001"}  # 다른 부서 사람


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.db import create_all
    from app.main import app

    create_all()
    with TestClient(app) as c:
        # 부서 하나 + 담당자 한 명 + 부서원 한 명
        c.post("/api/departments", headers=ADMIN,
               json={"code": "SW1", "name": "SW개발팀"})
        c.post("/api/departments/SW1/members", headers=ADMIN,
               json={"user_id": "D1001", "role": "manager"})
        c.post("/api/departments/SW1/members", headers=ADMIN,
               json={"user_id": "D1002", "role": "member"})
        yield c


@pytest.fixture(scope="module")
def dept_app(client):
    """SW개발팀의 부서 공통 앱 하나. 주소는 가짜라 status 는 unreachable 입니다."""
    r = client.post(
        "/api/apps",
        headers=MANAGER,
        json={
            "slug": "sw1-legacy",
            "name": "SW팀 레거시 조회",
            "endpoint": "http://127.0.0.1:9/mcp",
            "visibility": "department",
            "owner_dept_code": "SW1",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_부서는_관리자만_만듭니다(client):
    r = client.post("/api/departments", headers=MEMBER,
                    json={"code": "X9", "name": "몰래부서"})
    assert r.status_code == 403


def test_부서원은_부서_공통_앱이_보입니다(client, dept_app):
    names = [a["slug"] for a in client.get("/api/apps", headers=MEMBER).json()]
    assert "sw1-legacy" in names


def test_부서_밖_사람에게는_안_보입니다(client, dept_app):
    names = [a["slug"] for a in client.get("/api/apps", headers=OUTSIDER).json()]
    assert "sw1-legacy" not in names
    assert client.get(f"/api/apps/{dept_app['id']}", headers=OUTSIDER).status_code == 404


def test_부서_공통_앱은_담당자만_등록합니다(client):
    r = client.post(
        "/api/apps",
        headers=MEMBER,
        json={
            "slug": "sw1-nope",
            "name": "부서원이 올린 부서앱",
            "endpoint": "http://127.0.0.1:9/mcp",
            "visibility": "department",
            "owner_dept_code": "SW1",
        },
    )
    assert r.status_code == 403


def test_없는_부서로는_등록할_수_없습니다(client):
    r = client.post(
        "/api/apps",
        headers=ADMIN,
        json={
            "slug": "ghost-dept-app",
            "name": "없는 부서 앱",
            "endpoint": "http://127.0.0.1:9/mcp",
            "visibility": "department",
            "owner_dept_code": "없는코드",
        },
    )
    assert r.status_code == 404


def test_부서_공통_카드는_부서원_전원에게_보입니다(client):
    made = client.post(
        "/api/cards",
        headers=MANAGER,
        json={"title": "주간보고 모음", "dept_code": "SW1"},
    )
    assert made.status_code == 201, made.text
    assert made.json()["dept_name"] == "SW개발팀"

    seen = client.get("/api/cards", headers=MEMBER).json()
    titles = [c["title"] for c in seen]
    assert "주간보고 모음" in titles
    # 부서원은 볼 수만 있고 고치지는 못합니다.
    card = next(c for c in seen if c["title"] == "주간보고 모음")
    assert card["editable"] is False

    # 부서 밖 사람에게는 아예 없는 카드입니다.
    outside = [c["title"] for c in client.get("/api/cards", headers=OUTSIDER).json()]
    assert "주간보고 모음" not in outside
    assert client.delete(f"/api/cards/{card['id']}", headers=OUTSIDER).status_code == 404
    assert client.delete(f"/api/cards/{card['id']}", headers=MEMBER).status_code == 403


def test_개인_카드는_예전처럼_나만_봅니다(client):
    made = client.post("/api/cards", headers=MEMBER, json={"title": "내 개인 카드"})
    assert made.status_code == 201
    assert made.json()["dept_code"] == ""
    assert made.json()["editable"] is True

    mine = [c["title"] for c in client.get("/api/cards", headers=MEMBER).json()]
    assert "내 개인 카드" in mine
    others = [c["title"] for c in client.get("/api/cards", headers=MANAGER).json()]
    assert "내 개인 카드" not in others


def test_부서_공통_카드는_담당자만_만듭니다(client):
    r = client.post("/api/cards", headers=MEMBER,
                    json={"title": "부서원이 만든 공통 카드", "dept_code": "SW1"})
    assert r.status_code == 403


def test_오케스트레이터_후보에도_같은_규칙이_적용됩니다(client, dept_app):
    """목록에서 막고 실행에서 안 막으면 구멍입니다. 실제 후보 목록으로 확인합니다."""
    from app.db import SessionLocal
    from app.models import App, AppStatus, AppTool
    from app.orchestrator.engine import load_bindings

    db = SessionLocal()
    try:
        # 가짜 주소라 기능 목록을 못 읽어 왔습니다. 후보에 들도록 손으로 한 개 넣습니다.
        app_row = db.get(App, dept_app["id"])
        app_row.status = AppStatus.active
        if not app_row.tools:
            db.add(AppTool(app_id=app_row.id, name="search", description="조회"))
        db.commit()
        # expire_on_commit=False 라 방금 넣은 기능이 이 세션의 app_row 에는
        # 안 보입니다. 다시 읽어야 load_bindings 가 기능을 봅니다.
        db.refresh(app_row)

        member_apps = {b.app.slug for b in load_bindings(db, None, user_id="D1002")}
        outsider_apps = {b.app.slug for b in load_bindings(db, None, user_id="D2001")}
    finally:
        db.close()

    assert "sw1-legacy" in member_apps
    assert "sw1-legacy" not in outsider_apps


def test_후보_앱_목록은_부서로_갈립니다(client, dept_app):
    """역할 태그가 겹칠 때 부서 앱이 전사 공통 앱보다 먼저 뽑힙니다."""
    from app.models import App, AppVisibility
    from app.orchestrator.engine import pick_apps

    부서앱 = App(slug="sw1-legacy", name="SW팀 레거시 조회", capability_tag="레거시조회",
                visibility=AppVisibility.department, owner_dept_code="SW1",
                owner_user_id="D1001")
    공식앱 = App(slug="corp-legacy", name="전사 레거시 조회", capability_tag="레거시조회",
                visibility=AppVisibility.approved, owner_user_id="E9999")

    부서원 = pick_apps([공식앱, 부서앱], user_id="D1002", my_dept_codes={"SW1"})
    assert [a.slug for a in 부서원] == ["sw1-legacy"]

    남 = pick_apps([공식앱, 부서앱], user_id="D2001", my_dept_codes=set())
    assert [a.slug for a in 남] == ["corp-legacy"]


def test_부서에_앱이_남아_있으면_부서를_못_지웁니다(client, dept_app):
    r = client.delete("/api/departments/SW1", headers=ADMIN)
    assert r.status_code == 409
    assert "남아" in r.json()["detail"]


def test_부서_공통을_풀면_개인용으로_돌아갑니다(client):
    made = client.post(
        "/api/apps",
        headers=MANAGER,
        json={
            "slug": "sw1-temp",
            "name": "잠깐 부서앱",
            "endpoint": "http://127.0.0.1:9/mcp",
            "visibility": "department",
            "owner_dept_code": "SW1",
        },
    ).json()
    back = client.post(f"/api/apps/{made['id']}/unshare-dept", headers=MANAGER).json()
    assert back["visibility"] == "private"
    assert back["owner_dept_code"] == ""
    names = [a["slug"] for a in client.get("/api/apps", headers=MEMBER).json()]
    assert "sw1-temp" not in names
