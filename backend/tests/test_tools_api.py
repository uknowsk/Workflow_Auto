"""도구 서랍 저장소(메모·그림) 확인.

조용히 틀리면 사고가 되는 두 가지만 봅니다.
  1) 남의 메모·그림이 보이면 안 된다
  2) PNG 가 아니거나 너무 큰 그림은 받아 주면 안 된다
"""
from fastapi.testclient import TestClient

from app.api import tools


def _client():
    """메모리 DB 에 도구 API 만 올린 작은 앱.

    sqlite 의 :memory: 는 연결마다 다른 DB 라, 테스트 클라이언트가 다른 실을
    쓰면 방금 넣은 줄이 안 보입니다. StaticPool 로 연결 하나를 돌려 씁니다.
    """
    from fastapi import FastAPI
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.db import Base, get_db

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def _db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(tools.router)
    app.dependency_overrides[get_db] = _db
    return TestClient(app)


def _as(user_id: str) -> dict:
    # 개발용 헤더 로그인(DEV_HEADER_AUTH 기본값 true)
    return {"X-User-Id": user_id}


def test_메모는_적은_사람에게만_보인다():
    client = _client()
    client.post("/api/tools/notes", json={"title": "내 메모", "body": "x"}, headers=_as("a"))

    mine = client.get("/api/tools/notes", headers=_as("a")).json()
    others = client.get("/api/tools/notes", headers=_as("b")).json()

    assert [note["title"] for note in mine] == ["내 메모"]
    assert others == []


def test_남의_메모는_고치지도_지우지도_못한다():
    client = _client()
    note = client.post(
        "/api/tools/notes", json={"title": "비밀", "body": ""}, headers=_as("a")
    ).json()

    changed = client.put(
        f"/api/tools/notes/{note['id']}",
        json={"title": "덮어쓰기", "body": ""},
        headers=_as("b"),
    )
    removed = client.delete(f"/api/tools/notes/{note['id']}", headers=_as("b"))

    assert changed.status_code == 404
    assert removed.status_code == 404


def test_PNG_가_아니면_저장하지_않는다():
    client = _client()
    answer = client.post(
        "/api/tools/drawings",
        json={"title": "가짜", "image": "그냥 글자", "width": 10, "height": 10},
        headers=_as("a"),
    )
    assert answer.status_code == 400


def test_너무_큰_그림은_거절한다():
    client = _client()
    huge = "data:image/png;base64," + "A" * (tools.MAX_DRAWING_BYTES + 1)
    answer = client.post(
        "/api/tools/drawings",
        json={"title": "큰 그림", "image": huge, "width": 1600, "height": 1000},
        headers=_as("a"),
    )
    assert answer.status_code == 400


def test_그림은_저장한_그대로_돌아온다():
    client = _client()
    image = "data:image/png;base64,iVBORw0KGgo="
    saved = client.post(
        "/api/tools/drawings",
        json={"title": "흐름도", "image": image, "width": 1600, "height": 1000},
        headers=_as("a"),
    ).json()

    # 목록에는 그림 자체가 실리지 않습니다(목록이 무거워지지 않게).
    listed = client.get("/api/tools/drawings", headers=_as("a")).json()
    assert "image" not in listed[0]

    full = client.get(f"/api/tools/drawings/{saved['id']}", headers=_as("a")).json()
    assert full["image"] == image
