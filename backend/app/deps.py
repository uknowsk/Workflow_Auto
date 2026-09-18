"""사용자 식별과 권한.

읽는 순서
  1) Authorization: Bearer <토큰>  - 정상 로그인
  2) X-User-Id 헤더               - 개발 편의용. DEV_HEADER_AUTH=false 면 막힙니다.

사내 SSO 로 바꿀 때는 app/auth/backend.py 의 SsoBackend 만 채우면 되고
이 파일은 그대로 둬도 됩니다.
"""
from fastapi import Depends, Header, HTTPException

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


def is_admin(user_id: str) -> bool:
    """환경변수 ADMIN_USER_IDS 에 있으면 관리자입니다.

    계정의 is_admin 플래그는 로그인 토큰에 담겨 오는데, 환경변수 쪽을
    같이 보는 이유는 "DB가 비어 있어도 관리자가 들어갈 수 있게" 하기 위해서입니다.
    """
    return user_id in get_settings().admins


def require_admin(
    user_id: str = Depends(current_user),
    token_admin: bool = Depends(is_admin_token),
) -> str:
    if not (token_admin or is_admin(user_id)):
        raise HTTPException(403, "관리자만 할 수 있습니다.")
    return user_id
