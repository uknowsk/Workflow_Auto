"""사용자 식별과 권한.

읽는 순서
  1) Authorization: Bearer <토큰>  - 정상 로그인
  2) X-User-Id 헤더               - 개발 편의용. DEV_HEADER_AUTH=false 면 막힙니다.

사내 SSO 로 바꿀 때는 app/auth/backend.py 의 SsoBackend 만 채우면 되고
이 파일은 그대로 둬도 됩니다.
"""
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.auth.backend import is_configured_admin
from app.auth.tokens import read_token
from app.config import get_settings


def current_user(
    authorization: str = Header(default=""),
    x_user_id: str = Header(default=""),
) -> str:
    settings = get_settings()

    if authorization.lower().startswith("bearer "):
        data = read_token(authorization[7:].strip())
        if data is None:
            raise HTTPException(401, "로그인이 만료되었습니다. 다시 로그인해 주세요.")
        return str(data["sub"])

    if x_user_id and settings.dev_header_auth:
        return x_user_id

    raise HTTPException(401, "로그인이 필요합니다.")


def is_admin_token(authorization: str = Header(default="")) -> bool:
    if authorization.lower().startswith("bearer "):
        data = read_token(authorization[7:].strip())
        if data:
            return bool(data.get("adm"))
    return False


def is_admin(user_id: str, db: Session | None = None) -> bool:
    """이 사번이 관리자인지. 두 군데를 봅니다.

      1) 환경변수 ADMIN_USER_IDS(사번) / ADMIN_SSO_IDS(SSO 아이디)
         - DB 가 비어 있어도 관리자가 들어올 수 있게 하는 장치입니다.
      2) 계정의 is_admin 플래그 (.env 의 ADMIN_ID 로 만들어진 첫 관리자 포함)

    2번을 같이 보는 이유: 관리자 계정으로 로그인했는데 환경변수에 사번이 없다고
    부서 관리 같은 기능이 막히면 아무도 원인을 짐작하지 못합니다.
    db 를 넘기면 그 세션을 쓰고, 없으면 잠깐 하나 열었다 닫습니다.
    """
    if is_configured_admin(user_id):
        return True
    if not user_id:
        return False

    from app.db import SessionLocal  # 순환 import 를 피하려고 여기서 읽습니다
    from app.models import User

    session = db or SessionLocal()
    try:
        user = session.query(User).filter(User.user_id == user_id).first()
        return bool(user and user.is_admin)
    finally:
        if db is None:
            session.close()


def require_admin(
    user_id: str = Depends(current_user),
    token_admin: bool = Depends(is_admin_token),
) -> str:
    if not (token_admin or is_admin(user_id)):
        raise HTTPException(403, "관리자만 할 수 있습니다.")
    return user_id
