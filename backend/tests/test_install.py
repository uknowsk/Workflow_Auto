"""앱스토어의 «설치»(= 내 에이전트에 담기).

여기서 조용히 틀리면 생기는 일
  - 두 번 눌렀을 때 카드가 두 장 생겨서, 내 에이전트가 지저분해집니다.
  - 남의 개인용 앱을 설치할 수 있으면, 목록에는 안 보이는 앱이 내 카드에 들어옵니다.
  - «빼기»가 여러 앱을 묶어 만든 카드까지 지우면, 사용자가 꾸며 둔 것이 날아갑니다.

환경(파일 하나짜리 sqlite + 관리자 E9999)은 tests/conftest.py 에서 정합니다.
"""
import pytest

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
    from app.db import SessionLocal
    from app.models import App, AppVisibility

    db = SessionLocal()
    try:
        row = App(
            slug=slug,
            name=f"{slug} 앱",
            usage_hint="이럴 때 씁니다",
            owner_user_id=owner,
            endpoint=DEAD,
            visibility=AppVisibility(visibility),
        )
        db.add(row)
        db.commit()
        return row.id
    finally:
        db.close()


def _cards(client, user_id: str) -> list[dict]:
    return client.get("/api/cards", headers={"X-User-Id": user_id}).json()


def test_설치하면_그_앱만_쓰는_카드가_생깁니다(client):
    app_id = _make_app("install-a", "E2001")

    r = client.post(f"/api/apps/{app_id}/install", headers={"X-User-Id": "E1001"})
    assert r.status_code == 201
    card = r.json()
    assert card["app_ids"] == [app_id]
    assert card["title"] == "install-a 앱"
    # 무엇을 시킬지는 그때그때 다르므로 요청문은 비어 있고, 대신 앱 설명이 들어갑니다.
    assert card["prompt_template"] == ""
    assert card["description"] == "이럴 때 씁니다"

    assert [c["id"] for c in _cards(client, "E1001")] == [card["id"]]
    assert client.get(
        "/api/apps/installed/ids", headers={"X-User-Id": "E1001"}
    ).json() == [app_id]


def test_두_번_눌러도_카드는_한_장입니다(client):
    app_id = _make_app("install-b", "E2001")
    first = client.post(f"/api/apps/{app_id}/install", headers={"X-User-Id": "E1002"})
    second = client.post(f"/api/apps/{app_id}/install", headers={"X-User-Id": "E1002"})

    assert first.json()["id"] == second.json()["id"]
    assert len(_cards(client, "E1002")) == 1


def test_남의_개인용_앱은_설치할_수_없습니다(client):
    app_id = _make_app("install-c", "E2002", visibility="private")

    r = client.post(f"/api/apps/{app_id}/install", headers={"X-User-Id": "E1003"})
    assert r.status_code == 404
    assert _cards(client, "E1003") == []


def test_빼기는_설치한_카드만_지웁니다(client):
    app_id = _make_app("install-d", "E2001")
    other = _make_app("install-e", "E2001")

    client.post(f"/api/apps/{app_id}/install", headers={"X-User-Id": "E1004"})
    # 사용자가 손으로 꾸민, 앱 두 개를 묶은 카드. 빼기가 이걸 건드리면 안 됩니다.
    mine = client.post(
        "/api/cards",
        headers={"X-User-Id": "E1004"},
        json={"title": "내가 만든 묶음", "app_ids": [app_id, other]},
    ).json()

    r = client.delete(f"/api/apps/{app_id}/install", headers={"X-User-Id": "E1004"})
    assert r.status_code == 204

    left = _cards(client, "E1004")
    assert [c["id"] for c in left] == [mine["id"]]
    assert client.get(
        "/api/apps/installed/ids", headers={"X-User-Id": "E1004"}
    ).json() == []


def test_설치하지_않은_앱을_빼면_404(client):
    app_id = _make_app("install-f", "E2001")
    r = client.delete(f"/api/apps/{app_id}/install", headers={"X-User-Id": "E1005"})
    assert r.status_code == 404
