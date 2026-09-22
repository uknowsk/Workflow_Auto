"""대시보드의 프로젝트 칸.

이 칸만 다른 칸과 다르게, 앱이 돌려준 글을 그대로 보여 주지 않고 JSON 을 풀어
화면이 시간축으로 그릴 수 있게 넘깁니다. 그 풀어 주는 부분이 조용히 틀리면
화면에는 "빈 칸"으로만 보여서 원인을 찾기 어렵습니다.
"""
import asyncio
import json

import pytest

from app.api import dashboard as dash

WIDGET = {
    "key": "my_projects",
    "title": "등록된 프로젝트",
    "icon": "📁",
    "capability_tag": "개발프로젝트관리",
    "tool": "list_my_projects",
    "arguments": {"user_id": "{{user_id}}"},
    "render": "projects",
}


class _Tool:
    name = "list_my_projects"


class _App:
    name = "개발 프로젝트 관리"
    endpoint = "http://app-dev-projects:9111/mcp"
    auth_headers: dict = {}
    tools = [_Tool()]


def _answer(monkeypatch, payload: str, is_error: bool = False):
    monkeypatch.setattr(dash, "_pick_app", lambda db, tag, user_id: _App())

    async def fake_call(*args, **kwargs):
        return payload, is_error

    monkeypatch.setattr(dash.mcp, "call_tool", fake_call)
    return asyncio.run(dash._fetch_widget(None, WIDGET, "E1001", "김로아"))


def test_프로젝트_칸은_앱이_준_JSON_을_풀어서_넘긴다(monkeypatch):
    payload = json.dumps(
        {"count": 1, "projects": [{"id": "p1", "model": "SM-X100", "stage": "구현"}]},
        ensure_ascii=False,
    )
    result = _answer(monkeypatch, payload)

    assert result["status"] == "ok"
    assert result["render"] == "projects"
    assert result["data"]["projects"][0]["model"] == "SM-X100"


def test_등록된_프로젝트가_없으면_빈_칸이_된다(monkeypatch):
    result = _answer(monkeypatch, json.dumps({"count": 0, "projects": []}))

    assert result["status"] == "empty"


def test_JSON_이_아니면_글로라도_보여_준다(monkeypatch):
    result = _answer(monkeypatch, "프로젝트 2건")

    assert result["status"] == "ok"
    assert result["data"] is None and result["text"] == "프로젝트 2건"


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.db import create_all
    from app.main import app

    create_all()
    with TestClient(app) as c:
        yield c


def test_프로젝트_앱이_없으면_이유를_알려_준다(client):
    r = client.post(
        "/api/dashboard/projects",
        headers={"X-User-Id": "E1001"},
        json={"name": "차세대 단말", "model": "SM-X100"},
    )

    assert r.status_code == 400
    assert "개발프로젝트관리" in r.json()["detail"]


def test_이름_없이는_프로젝트를_못_만든다(client):
    r = client.post(
        "/api/dashboard/projects", headers={"X-User-Id": "E1001"}, json={"name": " "}
    )

    assert r.status_code == 400
