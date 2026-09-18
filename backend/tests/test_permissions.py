"""누가 무엇을 볼 수 있는지 확인합니다.

- "이달의 앱"(앱 순위)은 관리자만 봅니다. 일반 사용자가 주소를 직접 쳐도 막혀야 합니다.
- 화면 테마는 개인 계정에 저장되어야 합니다(다른 PC 에서 들어와도 같은 모양).

여기만 조용히 틀리면 일반 사용자에게 남의 앱 사용량이 그대로 보입니다.
"""
import os
import tempfile

import pytest

# 앱을 import 하기 전에 환경을 정해 둡니다(파일 하나짜리 sqlite + 관리자 한 명).
_DB = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{_DB}"
os.environ["ADMIN_USER_IDS"] = "E9999"
os.environ["DEV_HEADER_AUTH"] = "true"
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["HEALTHCHECK_INTERVAL_SECONDS"] = "0"
os.environ["SEED_FILE"] = ""


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.db import create_all
    from app.main import app

    create_all()
    with TestClient(app) as c:
        yield c


def test_일반_사용자는_앱_순위를_볼_수_없습니다(client):
    r = client.get("/api/stats/apps", headers={"X-User-Id": "E1001"})
    assert r.status_code == 403


def test_관리자는_앱_순위를_볼_수_있습니다(client):
    r = client.get("/api/stats/apps", headers={"X-User-Id": "E9999"})
    assert r.status_code == 200
    assert "ranking" in r.json()


def test_대시보드는_일반_사용자에게_순위를_담지_않습니다(client):
    r = client.get("/api/dashboard", headers={"X-User-Id": "E1001"})
    assert r.status_code == 200
    assert r.json()["ranking"] == []


def test_테마는_계정에_저장됩니다(client):
    # 계정이 있어야 저장됩니다. 관리자가 하나 만들어 줍니다.
    client.post(
        "/api/auth/users",
        headers={"X-User-Id": "E9999"},
        json={"user_id": "E1002", "password": "pw", "name": "테스터"},
    )
    saved = client.put(
        "/api/auth/me/settings", headers={"X-User-Id": "E1002"}, json={"theme": "white"}
    )
    assert saved.status_code == 200
    assert saved.json()["theme"] == "white"
    assert client.get("/api/auth/me", headers={"X-User-Id": "E1002"}).json()["theme"] == "white"


def test_없는_테마는_거절합니다(client):
    r = client.put(
        "/api/auth/me/settings",
        headers={"X-User-Id": "E1002"},
        json={"theme": "어디서왔니"},
    )
    assert r.status_code == 400
