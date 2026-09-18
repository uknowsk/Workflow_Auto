"""관리자 계정 자동 생성 테스트.

.env 의 ADMIN_ID / ADMIN_PASSWORD 로 관리자가 만들어지는지, 값이 없으면
아무 계정도 안 생기는지, 이미 있는 계정의 비밀번호를 함부로 덮어쓰지 않는지
확인합니다. 여기가 틀리면 아무도 로그인 못 하거나, 반대로 사용자가 바꾼
비밀번호가 기동할 때마다 되돌아갑니다.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import seed as seed_module
from app.auth.backend import is_configured_admin
from app.auth.passwords import hash_password, verify_password
from app.config import Settings, get_settings
from app.db import Base
from app.models import User


@pytest.fixture()
def session_factory(tmp_path):
    """테스트마다 새 sqlite 파일 하나. 진짜 DB 는 건드리지 않습니다."""
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'test.db'}", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _seed(monkeypatch, session_factory, **env) -> None:
    monkeypatch.setattr(seed_module, "SessionLocal", session_factory)
    monkeypatch.setattr(seed_module, "settings", Settings(_env_file=None, **env))
    seed_module.seed_bootstrap_admin()


def test_환경변수가_있으면_관리자가_만들어집니다(monkeypatch, session_factory):
    _seed(monkeypatch, session_factory, admin_id="admin", admin_password="열려라참깨")

    db = session_factory()
    user = db.query(User).filter(User.user_id == "admin").one()
    assert user.is_admin is True
    assert verify_password("열려라참깨", user.password_hash)
    # 원문 비밀번호는 저장하지 않습니다.
    assert "열려라참깨" not in user.password_hash


def test_환경변수가_없으면_아무것도_안_만듭니다(monkeypatch, session_factory):
    _seed(monkeypatch, session_factory)
    # 아이디만 있고 비밀번호가 없어도 만들지 않습니다.
    _seed(monkeypatch, session_factory, admin_id="admin")

    db = session_factory()
    assert db.query(User).count() == 0


def test_이미_있으면_비밀번호를_덮어쓰지_않습니다(monkeypatch, session_factory):
    db = session_factory()
    db.add(User(user_id="admin", is_admin=True, password_hash=hash_password("내가바꾼비번")))
    db.commit()

    _seed(monkeypatch, session_factory, admin_id="admin", admin_password="옛날비번")

    user = session_factory().query(User).filter(User.user_id == "admin").one()
    assert verify_password("내가바꾼비번", user.password_hash)


def test_초기화_플래그를_켜면_비밀번호를_바꿉니다(monkeypatch, session_factory):
    db = session_factory()
    db.add(User(user_id="admin", is_admin=True, password_hash=hash_password("잊어버린비번")))
    db.commit()

    _seed(
        monkeypatch,
        session_factory,
        admin_id="admin",
        admin_password="새비번",
        admin_reset_password=True,
    )

    user = session_factory().query(User).filter(User.user_id == "admin").one()
    assert verify_password("새비번", user.password_hash)


def test_SSO_아이디_목록에_있으면_관리자입니다(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("ADMIN_SSO_IDS", "sk1980.kim, other.id")
    try:
        assert is_configured_admin("sk1980.kim") is True
        # 대소문자는 가리지 않습니다.
        assert is_configured_admin("SK1980.Kim") is True
        assert is_configured_admin("남의아이디") is False
    finally:
        get_settings.cache_clear()
