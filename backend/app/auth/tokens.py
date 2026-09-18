"""로그인 토큰.

서버가 서명한 문자열 하나로 "이 사람은 누구다"를 증명합니다.
별도 저장소가 필요 없어 서버를 여러 대로 늘려도 그대로 동작합니다.
"""
import base64
import hmac
import json
import time
from hashlib import sha256

from app.config import get_settings


def _sign(payload: bytes) -> str:
    secret = get_settings().secret_key.encode()
    return hmac.new(secret, payload, sha256).hexdigest()


def create_token(user_id: str, is_admin: bool, ttl_seconds: int) -> str:
    payload = json.dumps(
        {"sub": user_id, "adm": is_admin, "exp": int(time.time()) + ttl_seconds},
        separators=(",", ":"),
    ).encode()
    body = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    return f"{body}.{_sign(payload)}"


def read_token(token: str) -> dict | None:
    """토큰이 우리가 서명한 것이고 아직 안 만료됐으면 내용을 돌려줍니다."""
    try:
        body, signature = token.split(".", 1)
        payload = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
        if not hmac.compare_digest(signature, _sign(payload)):
            return None
        data = json.loads(payload)
        if data.get("exp", 0) < time.time():
            return None
        return data
    except (ValueError, TypeError, json.JSONDecodeError):
        return None
