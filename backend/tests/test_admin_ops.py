"""운영하면서 실제로 눌러 보는 것들.

  - 관리자 화면의 '최근 오류'
  - 보관 기간 설정과 오래된 기록 정리
  - 계정 관리(비밀번호 초기화 / 퇴사자 끄기 / 부서 옮기기)
  - 작업 취소
  - Gauss 월 한도

여기가 조용히 틀리면, 관리자가 아무 일도 못 하는데 화면은 멀쩡해 보입니다.
환경(파일 하나짜리 sqlite + 관리자 E9999)은 tests/conftest.py 에서 정합니다.
"""
from datetime import datetime, timedelta, timezone

import pytest

ADMIN = {"X-User-Id": "E9999"}


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.db import create_all
    from app.main import app

    create_all()
    with TestClient(app) as c:
        yield c


# ── 최근 오류 ────────────────────────────────────────────────────────────────


def test_최근_오류는_관리자만_봅니다(client):
    assert client.get("/api/admin/errors", headers={"X-User-Id": "E1001"}).status_code == 403
    r = client.get("/api/admin/errors", headers=ADMIN)
    assert r.status_code == 200
    assert {"days", "runs", "app_calls", "apps_down"} <= set(r.json())


def test_실패한_실행이_최근_오류에_보입니다(client):
    from app.db import SessionLocal
    from app.models import Run, RunStatus

    db = SessionLocal()
    try:
        run = Run(
            user_id="E1001",
            request_text="지난주 회의록 요약해 줘",
            status=RunStatus.failed,
            error="TimeoutError: 앱이 응답하지 않습니다",
        )
        db.add(run)
        db.commit()
    finally:
        db.close()

    rows = client.get("/api/admin/errors", headers=ADMIN).json()["runs"]
    assert any("TimeoutError" in row["error"] for row in rows)


# ── 보관 기간과 정리 ─────────────────────────────────────────────────────────


def test_설정은_범위_밖이면_당겨_넣습니다(client):
    r = client.put(
        "/api/admin/settings", headers=ADMIN, json={"run_retention_days": 99999}
    )
    assert r.status_code == 200
    value = {row["key"]: row["value"] for row in r.json()}["run_retention_days"]
    assert value == 3650


def test_모르는_설정은_거절합니다(client):
    r = client.put("/api/admin/settings", headers=ADMIN, json={"없는값": 1})
    assert r.status_code == 400


def test_보관_기간이_지난_기록은_정리됩니다(client):
    from app.db import SessionLocal
    from app.models import Run, RunStatus

    client.put("/api/admin/settings", headers=ADMIN, json={"run_retention_days": 30})

    db = SessionLocal()
    try:
        db.add(
            Run(
                user_id="E1001",
                request_text="아주 오래된 요청",
                status=RunStatus.succeeded,
                created_at=datetime.now(timezone.utc) - timedelta(days=200),
            )
        )
        db.commit()
    finally:
        db.close()

    removed = client.post("/api/admin/cleanup", headers=ADMIN).json()["removed"]
    assert removed.get("runs", 0) >= 1

    # 방금 만든 최근 기록은 그대로 있어야 합니다.
    assert client.get("/api/admin/errors", headers=ADMIN).json()["runs"]


def test_0_이면_지우지_않습니다(client):
    from app import cleanup, settings_store
    from app.db import SessionLocal
    from app.models import Run, RunStatus

    db = SessionLocal()
    try:
        settings_store.set_value(db, "run_retention_days", 0)
        db.add(
            Run(
                user_id="E1001",
                request_text="오래됐지만 남아야 하는 기록",
                status=RunStatus.succeeded,
                created_at=datetime.now(timezone.utc) - timedelta(days=500),
            )
        )
        db.commit()
        assert cleanup.sweep_once(db).get("runs", 0) == 0
    finally:
        settings_store.set_value(db, "run_retention_days", 90)
        db.close()


# ── 계정 관리 ────────────────────────────────────────────────────────────────


def _make_user(client, user_id: str, **extra) -> None:
    client.post(
        "/api/auth/users",
        headers=ADMIN,
        json={"user_id": user_id, "password": "처음비번", "name": user_id, **extra},
    )


def test_계정_목록은_관리자만_봅니다(client):
    _make_user(client, "E2001", dept="SW개발팀")
    assert client.get("/api/auth/users", headers={"X-User-Id": "E2001"}).status_code == 403

    rows = client.get("/api/auth/users", headers=ADMIN).json()
    assert any(row["user_id"] == "E2001" for row in rows)

    찾기 = client.get("/api/auth/users?q=SW개발", headers=ADMIN).json()
    assert [row["user_id"] for row in 찾기] == ["E2001"]


def test_퇴사자를_끄면_로그인이_막힙니다(client):
    _make_user(client, "E2002")
    assert client.post(
        "/api/auth/login", json={"user_id": "E2002", "password": "처음비번"}
    ).status_code == 200

    r = client.patch("/api/auth/users/E2002", headers=ADMIN, json={"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] is False

    assert client.post(
        "/api/auth/login", json={"user_id": "E2002", "password": "처음비번"}
    ).status_code == 401


def test_비밀번호_초기화(client):
    _make_user(client, "E2003")
    r = client.post(
        "/api/auth/users/E2003/password", headers=ADMIN, json={"password": "새비번1234"}
    )
    assert r.status_code == 200

    assert client.post(
        "/api/auth/login", json={"user_id": "E2003", "password": "처음비번"}
    ).status_code == 401
    assert client.post(
        "/api/auth/login", json={"user_id": "E2003", "password": "새비번1234"}
    ).status_code == 200

    # 본인에게 알림 한 줄이 가 있어야 합니다.
    알림 = client.get("/api/notifications", headers={"X-User-Id": "E2003"}).json()
    assert any(n["kind"] == "password_reset" for n in 알림)


def test_부서_옮기기(client):
    client.post(
        "/api/departments",
        headers=ADMIN,
        json={"code": "D-OLD", "name": "예전팀"},
    )
    client.post(
        "/api/departments",
        headers=ADMIN,
        json={"code": "D-NEW", "name": "새팀"},
    )
    _make_user(client, "E2004", dept_code="D-OLD")

    r = client.patch("/api/auth/users/E2004", headers=ADMIN, json={"dept_code": "D-NEW"})
    assert r.status_code == 200
    assert r.json()["dept_codes"] == ["D-NEW"]


def test_없는_부서로는_옮기지_못합니다(client):
    _make_user(client, "E2005")
    r = client.patch(
        "/api/auth/users/E2005", headers=ADMIN, json={"dept_code": "그런부서없음"}
    )
    assert r.status_code == 404


def test_자기_계정은_끄지_못합니다(client):
    _make_user(client, "E9999")
    r = client.patch("/api/auth/users/E9999", headers=ADMIN, json={"is_active": False})
    assert r.status_code == 400


# ── 작업 취소 ────────────────────────────────────────────────────────────────


def test_실행을_취소하면_취소됨으로_남습니다(client):
    from app.db import SessionLocal
    from app.models import Run, RunStatus

    db = SessionLocal()
    try:
        run = Run(user_id="E1001", request_text="오래 걸리는 일", status=RunStatus.running)
        db.add(run)
        db.commit()
        run_id = run.id
    finally:
        db.close()

    r = client.post(f"/api/runs/{run_id}/cancel", headers={"X-User-Id": "E1001"})
    assert r.status_code == 200
    assert r.json()["status"] == "canceled"

    # 이미 끝난 일은 두 번 취소되지 않습니다.
    assert client.post(
        f"/api/runs/{run_id}/cancel", headers={"X-User-Id": "E1001"}
    ).status_code == 409


def test_남의_실행은_취소하지_못합니다(client):
    from app.db import SessionLocal
    from app.models import Run, RunStatus

    db = SessionLocal()
    try:
        run = Run(user_id="E1001", request_text="내 일", status=RunStatus.running)
        db.add(run)
        db.commit()
        run_id = run.id
    finally:
        db.close()

    assert client.post(
        f"/api/runs/{run_id}/cancel", headers={"X-User-Id": "E3001"}
    ).status_code in (403, 404)


# ── Gauss 한도 ───────────────────────────────────────────────────────────────


def test_한도가_0_이면_제한이_없습니다():
    from app import quota
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        assert quota.check(db, "E1001") == ""
    finally:
        db.close()


def test_한도를_넘으면_막고_관리자에게_한_번만_알립니다():
    from app import quota, settings_store
    from app.db import SessionLocal
    from app.models import LlmUsage, Notification

    db = SessionLocal()
    try:
        settings_store.set_value(db, "llm_monthly_token_limit", 1000)
        db.add(
            LlmUsage(
                user_id="E4001",
                total_tokens=1500,
                period=quota.current_period(),
            )
        )
        db.commit()

        막힌_말 = quota.check(db, "E4001")
        assert "한도" in 막힌_말

        quota.notify_admins_once(db, "E4001")
        quota.notify_admins_once(db, "E4001")
        보낸_알림 = (
            db.query(Notification)
            .filter(Notification.kind == "quota_exceeded")
            .all()
        )
        assert len(보낸_알림) == 1
    finally:
        settings_store.set_value(db, "llm_monthly_token_limit", 0)
        db.close()


# ── 출입증 유효시간 ───────────────────────────────────────────────────────────


def test_출입증은_2시간짜리입니다():
    from app.config import get_settings

    assert get_settings().token_ttl_seconds == 60 * 60 * 2


def test_쓰고_있으면_출입증이_연장됩니다(client):
    _make_user(client, "E5001")
    토큰 = client.post(
        "/api/auth/login", json={"user_id": "E5001", "password": "처음비번"}
    ).json()["token"]

    r = client.post("/api/auth/refresh", headers={"Authorization": f"Bearer {토큰}"})
    assert r.status_code == 200
    새_토큰 = r.json()["token"]

    # 새 출입증으로도 들어가져야 합니다.
    assert client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {새_토큰}"}
    ).status_code == 200


def test_꺼진_계정은_연장되지_않습니다(client):
    _make_user(client, "E5002")
    토큰 = client.post(
        "/api/auth/login", json={"user_id": "E5002", "password": "처음비번"}
    ).json()["token"]

    client.patch("/api/auth/users/E5002", headers=ADMIN, json={"is_active": False})

    # 이미 받아 간 출입증은 만료 전까지 살아 있지만, 더 늘려 주지는 않습니다.
    # 그래서 퇴사 처리는 늦어도 유효시간 안에 실제로 끊깁니다.
    r = client.post("/api/auth/refresh", headers={"Authorization": f"Bearer {토큰}"})
    assert r.status_code == 401
