"""앱 의견(VOC)과 앱 업데이트.

여기서 조용히 틀리면 생기는 일
  - 의견이 등록자에게 안 가서, 앱이 고쳐지지 않습니다.
  - 등록자가 마음에 안 드는 제보를 지울 수 있으면 의견함이 의미가 없습니다.
  - 업데이트 이력이 안 남으면, 잘못 올렸을 때 되돌릴 자리가 없습니다.

환경(파일 하나짜리 sqlite + 관리자 E9999)은 tests/conftest.py 에서 정합니다.
"""
import pytest

# 접속하자마자 거절당하는 주소. 앱에 실제로 접속해 보는 부분이 테스트를
# 붙잡고 있지 않도록, 일부러 아무도 안 듣고 있는 포트를 씁니다.
DEAD = "http://127.0.0.1:1/mcp"


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.db import create_all
    from app.main import app

    create_all()
    with TestClient(app) as c:
        yield c


def _make_app(slug: str, owner: str, visibility: str = "approved") -> str:
    """앱 한 개를 DB 에 바로 넣습니다(등록 API 는 앱에 접속을 시도하므로)."""
    from app.db import SessionLocal
    from app.models import App, AppVisibility

    db = SessionLocal()
    try:
        row = App(
            slug=slug,
            name=f"{slug} 앱",
            owner_user_id=owner,
            owner=owner,
            endpoint=DEAD,
            package_version="1.0",
            visibility=AppVisibility(visibility),
        )
        db.add(row)
        db.commit()
        return row.id
    finally:
        db.close()


def _notices(client, user_id: str) -> list[dict]:
    return client.get("/api/notifications", headers={"X-User-Id": user_id}).json()


def test_의견을_남기면_등록자에게_알림이_갑니다(client):
    app_id = _make_app("voc-a", "E2001")
    r = client.post(
        f"/api/apps/{app_id}/voc",
        headers={"X-User-Id": "E1001"},
        json={"kind": "bug", "title": "메일 보내기가 안 돼요", "body": "첨부가 있으면 실패합니다"},
    )
    assert r.status_code == 201
    voc = r.json()
    assert voc["status"] == "open"
    # 의견을 남긴 시점의 앱 버전이 같이 적혀야, 나중에 "그건 고쳤습니다"가 됩니다.
    assert voc["app_version"] == "1.0"

    titles = [n["title"] for n in _notices(client, "E2001")]
    assert any("의견이 왔습니다" in t for t in titles)


def test_남의_앱_의견에는_답변할_수_없습니다(client):
    app_id = _make_app("voc-b", "E2002")
    voc_id = client.post(
        f"/api/apps/{app_id}/voc",
        headers={"X-User-Id": "E1001"},
        json={"title": "느려요"},
    ).json()["id"]

    r = client.patch(
        f"/api/voc/{voc_id}",
        headers={"X-User-Id": "E1003"},  # 남
        json={"status": "done", "reply": "고쳤습니다"},
    )
    assert r.status_code == 403


def test_등록자가_답하면_쓴_사람에게_알림이_갑니다(client):
    app_id = _make_app("voc-c", "E2003")
    voc_id = client.post(
        f"/api/apps/{app_id}/voc",
        headers={"X-User-Id": "E1004"},
        json={"title": "엑셀이 깨져요", "rating": 3},
    ).json()["id"]

    r = client.patch(
        f"/api/voc/{voc_id}",
        headers={"X-User-Id": "E2003"},
        json={"status": "in_progress", "reply": "이번 주에 고치겠습니다"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "in_progress"
    assert r.json()["replied_by"] == "E2003"

    titles = [n["title"] for n in _notices(client, "E1004")]
    assert any("답이 왔습니다" in t for t in titles)


def test_등록자는_남이_쓴_의견을_지울_수_없습니다(client):
    app_id = _make_app("voc-d", "E2004")
    voc_id = client.post(
        f"/api/apps/{app_id}/voc",
        headers={"X-User-Id": "E1005"},
        json={"title": "결과가 이상합니다"},
    ).json()["id"]

    assert client.delete(f"/api/voc/{voc_id}", headers={"X-User-Id": "E2004"}).status_code == 403
    assert client.delete(f"/api/voc/{voc_id}", headers={"X-User-Id": "E1005"}).status_code == 204


def test_남의_개인용_앱에는_의견을_남길_수_없습니다(client):
    app_id = _make_app("voc-e", "E2005", visibility="private")
    r = client.post(
        f"/api/apps/{app_id}/voc",
        headers={"X-User-Id": "E1006"},
        json={"title": "안 보이는 앱"},
    )
    assert r.status_code == 404


def test_내_의견함과_보낸_의견이_나뉩니다(client):
    app_id = _make_app("voc-f", "E2006")
    client.post(
        f"/api/apps/{app_id}/voc",
        headers={"X-User-Id": "E1007"},
        json={"title": "글자가 잘립니다"},
    )
    inbox = client.get("/api/voc/inbox", headers={"X-User-Id": "E2006"}).json()
    sent = client.get("/api/voc/sent", headers={"X-User-Id": "E1007"}).json()
    assert [v["title"] for v in inbox] == ["글자가 잘립니다"]
    assert [v["title"] for v in sent] == ["글자가 잘립니다"]
    # 등록자 의견함에는 남의 앱 의견이 섞이면 안 됩니다.
    assert all(v["app_id"] == app_id for v in inbox)


def test_업데이트하면_이력이_쌓이고_되돌릴_수_있습니다(client):
    app_id = _make_app("voc-g", "E2007")

    r = client.post(
        f"/api/apps/{app_id}/update/endpoint",
        headers={"X-User-Id": "E2007"},
        json={"endpoint": DEAD, "version": "1.1", "note": "첨부 파일 오류 수정"},
    )
    assert r.status_code == 200
    assert r.json()["package_version"] == "1.1"

    versions = client.get(f"/api/apps/{app_id}/versions", headers={"X-User-Id": "E2007"}).json()
    # 처음 등록된 상태(1.0) + 방금 올린 1.1
    assert [v["version"] for v in versions] == ["1.1", "1.0"]
    assert versions[0]["is_current"] is True

    old = versions[1]["id"]
    back = client.post(
        f"/api/apps/{app_id}/versions/{old}/rollback", headers={"X-User-Id": "E2007"}
    )
    assert back.status_code == 200
    assert back.json()["package_version"] == "1.0"

    after = client.get(f"/api/apps/{app_id}/versions", headers={"X-User-Id": "E2007"}).json()
    # 되돌리기도 이력에 한 줄로 남습니다(지우지 않고 쌓기만).
    assert len(after) == 3
    assert after[0]["rolled_back_from"] == old


def test_남의_앱은_업데이트할_수_없습니다(client):
    app_id = _make_app("voc-h", "E2008")
    r = client.post(
        f"/api/apps/{app_id}/update/endpoint",
        headers={"X-User-Id": "E1008"},
        json={"endpoint": DEAD},
    )
    assert r.status_code == 403


def test_앱을_쓰는_사람에게_업데이트_알림이_갑니다(client):
    app_id = _make_app("voc-i", "E2009")
    # 이 앱을 자기 카드에 담아 둔 사람 = 업데이트에 영향받는 사람
    client.post(
        "/api/cards",
        headers={"X-User-Id": "E1009"},
        json={"title": "내 카드", "app_ids": [app_id]},
    )
    client.post(
        f"/api/apps/{app_id}/update/endpoint",
        headers={"X-User-Id": "E2009"},
        json={"endpoint": DEAD, "version": "2.0", "note": "속도 개선"},
    )
    titles = [n["title"] for n in _notices(client, "E1009")]
    assert any("업데이트됐습니다" in t for t in titles)
