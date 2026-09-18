"""비밀번호 해시.

원문은 절대 저장하지 않습니다. 표준 라이브러리만 써서 외부 의존성이 없습니다
(폐쇄망에서 설치할 게 하나라도 적은 편이 좋습니다).
"""
import hashlib
import hmac
import os

_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"pbkdf2_sha256${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
        # 타이밍 공격을 막으려고 단순 == 대신 이걸 씁니다.
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False
