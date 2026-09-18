"""사용자 식별과 권한.

뼈대 단계에서는 X-User-Id 헤더 하나로 사용자를 구분합니다.
사내에 붙일 때는 이 파일만 사내 SSO(헤더로 들어오는 사번 등)로 바꾸면
나머지 코드는 손댈 필요가 없습니다.

관리자는 환경변수 ADMIN_USER_IDS 에 사번을 적어 지정합니다.
"""
from fastapi import Depends, Header, HTTPException

from app.config import get_settings


def current_user(x_user_id: str = Header(default="demo")) -> str:
    return x_user_id


def is_admin(user_id: str) -> bool:
    return user_id in get_settings().admins


def require_admin(user_id: str = Depends(current_user)) -> str:
    """관리자만 통과시킵니다. 앱 승인/반려에 사용."""
    if not is_admin(user_id):
        raise HTTPException(403, "관리자만 할 수 있습니다.")
    return user_id
