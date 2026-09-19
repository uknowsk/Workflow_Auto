"""인증 백엔드 - 여기가 나중에 사내 SSO 로 바뀌는 자리입니다.

지금은 사번 + 비밀번호로 확인합니다(PasswordBackend).
사내 SSO 를 붙일 때는 아래 SsoBackend 를 채우고 AUTH_BACKEND=sso 로 바꾸면
나머지 코드는 손댈 필요가 없습니다.
"""
from __future__ import annotations

from typing import Protocol

from sqlalchemy.orm import Session

from app.auth.passwords import verify_password
from app.config import get_settings
from app.models import User


def is_configured_admin(user_id: str) -> bool:
    """환경변수로 관리자라고 지정해 둔 아이디인지 봅니다.

    두 군데를 봅니다.
      ADMIN_USER_IDS  사번 목록 (예: E1001,E2001)
      ADMIN_SSO_IDS   사내 SSO 아이디 목록 (예: sk1980.kim)
    DB 가 비어 있어도, SSO 로 처음 들어온 사람이라도 관리자로 들어올 수 있게 하는 장치입니다.
    """
    settings = get_settings()
    return user_id in settings.admins or user_id.strip().lower() in settings.admin_sso


def apply_admin_role(db: Session, user: User) -> User:
    """ADMIN_USER_IDS / ADMIN_SSO_IDS 에 있는 사람은 로그인할 때 관리자 역할을 답니다."""
    if not user.is_admin and is_configured_admin(user.user_id):
        user.is_admin = True
        db.commit()
    return user


class AuthBackend(Protocol):
    def authenticate(self, db: Session, user_id: str, password: str) -> User | None:
        ...


class PasswordBackend:
    """사번 + 비밀번호. 뼈대의 기본값."""

    def authenticate(self, db: Session, user_id: str, password: str) -> User | None:
        user = db.query(User).filter(User.user_id == user_id).first()
        if user is None or not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return apply_admin_role(db, user)


class SsoBackend:
    """사내 SSO 를 붙일 자리.

    보통 이런 모양이 됩니다.
      1) 사용자를 사내 SSO 로그인 페이지로 보낸다
      2) 돌아올 때 받은 토큰을 사내 인증 서버에 물어 사번을 확인한다
      3) users 표에 없으면 새로 만들고, 있으면 그 사용자를 돌려준다
      4) 돌려주기 전에 apply_admin_role(db, user) 을 부른다
         - ADMIN_SSO_IDS 에 적힌 아이디(예: sk1980.kim)는 여기서 관리자가 됩니다

    2번의 확인 방법(OIDC? SAML? 사내 전용 헤더?)만 확인되면 20줄이면 됩니다.
    그때까지는 PasswordBackend 를 씁니다.
    """

    def authenticate(self, db: Session, user_id: str, password: str) -> User | None:
        raise NotImplementedError(
            "사내 SSO 연동은 아직입니다. AUTH_BACKEND=password 로 두세요."
        )


def get_backend(name: str) -> AuthBackend:
    return SsoBackend() if name == "sso" else PasswordBackend()
