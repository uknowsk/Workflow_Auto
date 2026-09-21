"""저장할 때 잠그고 읽을 때 푸는 자물쇠.

앱을 등록할 때 넣는 접속 정보(토큰, 비밀번호가 든 헤더)는 DB 에 그대로 두면
DB 를 한 번 내려받는 것만으로 등록된 앱 전부의 열쇠가 같이 나갑니다.
그래서 넣기 전에 잠그고, 실제로 앱을 부를 때만 풉니다.

열쇠는 `.env` 의 ENCRYPTION_KEY 입니다. 안 정했으면 SECRET_KEY 를 같이 씁니다.
**열쇠를 바꾸면 이미 저장해 둔 접속 정보는 못 풉니다.** 그때는 앱 등록 화면에서
접속 정보를 다시 넣어야 합니다(그래서 로그인 열쇠와 따로 둘 수 있게 했습니다).
"""
from __future__ import annotations

import base64
import json
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.config import get_settings

# 잠긴 값임을 알아보는 표시. 이 열쇠가 있으면 잠긴 것, 없으면 옛날에 그냥 저장된 것.
SEALED_KEY = "__enc__"

# 열쇠를 늘여 만들 때 쓰는 고정값. 비밀이 아니어도 됩니다(열쇠 자체가 비밀).
# 고정이라 같은 열쇠는 늘 같은 자물쇠가 되고, 서버가 여러 대여도 서로 풉니다.
_SALT = b"workflow-auto-app-secrets-v1"
_ITERATIONS = 200_000


class SecretUnreadable(RuntimeError):
    """잠긴 값을 못 풀었을 때. 보통 ENCRYPTION_KEY 가 바뀐 경우입니다."""


@lru_cache(maxsize=4)
def _cipher(key: str) -> Fernet:
    derived = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32, salt=_SALT, iterations=_ITERATIONS
    ).derive(key.encode())
    return Fernet(base64.urlsafe_b64encode(derived))


def _current() -> Fernet:
    return _cipher(get_settings().crypto_key)


def seal(value: dict | None) -> dict:
    """저장할 모양으로 잠급니다. 빈 값은 잠글 것이 없으니 그대로 둡니다."""
    if not value:
        return {}
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    return {SEALED_KEY: _current().encrypt(payload).decode()}


def unseal(stored: dict | None) -> dict:
    """저장된 모양을 풉니다.

    아직 안 잠긴 옛 데이터(그냥 dict)는 그대로 돌려줍니다. 그래야 이 기능을
    올리는 순간 기존 앱들이 멈추지 않습니다. 옛 데이터는 scripts/seal_secrets.py
    로 한 번에 잠글 수 있고, 앱을 수정해 저장해도 그때 잠깁니다.
    """
    if not isinstance(stored, dict) or not stored:
        return {}
    token = stored.get(SEALED_KEY)
    if token is None:
        return stored
    try:
        return json.loads(_current().decrypt(str(token).encode()).decode())
    except (InvalidToken, ValueError, TypeError) as exc:
        raise SecretUnreadable(
            "앱 접속 정보를 풀지 못했습니다. .env 의 ENCRYPTION_KEY 가 "
            "저장할 때와 달라졌는지 확인하고, 그렇다면 앱 등록 화면에서 "
            "접속 정보를 다시 넣어 주세요."
        ) from exc


def is_sealed(stored: dict | None) -> bool:
    return isinstance(stored, dict) and SEALED_KEY in stored
