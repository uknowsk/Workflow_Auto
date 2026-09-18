"""인증 백엔드 - 여기가 나중에 사내 SSO 로 바뀌는 자리입니다.

지금은 사번 + 비밀번호로 확인합니다(PasswordBackend).
사내 SSO 를 붙일 때는 아래 SsoBackend 를 채우고 AUTH_BACKEND=sso 로 바꾸면
나머지 코드는 손댈 필요가 없습니다.
"""
from __future__ import annotations

from typing import Protocol

from sqlalchemy.orm import Session

from app.auth.passwords import verify_password
from app.models import User


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
        return user


class SsoBackend:
    """사내 SSO 를 붙일 자리.

    보통 이런 모양이 됩니다.
      1) 사용자를 사내 SSO 로그인 페이지로 보낸다
      2) 돌아올 때 받은 토큰을 사내 인증 서버에 물어 사번을 확인한다
      3) users 표에 없으면 새로 만들고, 있으면 그 사용자를 돌려준다

    2번의 확인 방법(OIDC? SAML? 사내 전용 헤더?)만 확인되면 20줄이면 됩니다.
    그때까지는 PasswordBackend 를 씁니다.
    """

    def authenticate(self, db: Session, user_id: str, password: str) -> User | None:
        raise NotImplementedError(
            "사내 SSO 연동은 아직입니다. AUTH_BACKEND=password 로 두세요."
        )


def get_backend(name: str) -> AuthBackend:
    return SsoBackend() if name == "sso" else PasswordBackend()
