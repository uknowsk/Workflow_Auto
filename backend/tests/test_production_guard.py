"""운영 설정 점검과 앱 접속 정보 잠그기.

둘 다 "조용히 틀리면 사고가 나는" 자리라 테스트로 못을 박아 둡니다.
"""
from __future__ import annotations

import pytest

from app import crypto
from app.config import (
    DEFAULT_SECRET_KEY,
    Settings,
    UnsafeProductionSettings,
    check_production_safety,
    production_problems,
)

SAFE = dict(
    app_env="production",
    dev_header_auth=False,
    secret_key="x" * 40,
    cors_origins="http://workflow.example.net",
)


def test_개발환경은_아무것도_막지_않는다():
    settings = Settings(app_env="dev", dev_header_auth=True, secret_key=DEFAULT_SECRET_KEY,
                        cors_origins="*")
    assert production_problems(settings) == []
    check_production_safety(settings)  # 예외가 나면 안 됩니다


def test_안전하게_채우면_통과한다():
    settings = Settings(**SAFE)
    assert production_problems(settings) == []
    check_production_safety(settings)


@pytest.mark.parametrize(
    "override, 찍혀야_할_말",
    [
        ({"dev_header_auth": True}, "DEV_HEADER_AUTH"),
        ({"secret_key": DEFAULT_SECRET_KEY}, "SECRET_KEY"),
        ({"secret_key": "짧음"}, "SECRET_KEY"),
        ({"cors_origins": "*"}, "CORS_ORIGINS"),
        ({"cors_origins": "http://a.net,*"}, "CORS_ORIGINS"),
        ({"cors_origins": ""}, "CORS_ORIGINS"),
    ],
)
def test_위험한_설정이면_서버가_안_뜬다(override, 찍혀야_할_말):
    settings = Settings(**{**SAFE, **override})
    problems = production_problems(settings)
    assert len(problems) == 1
    assert 찍혀야_할_말 in problems[0]

    with pytest.raises(UnsafeProductionSettings) as caught:
        check_production_safety(settings)
    # 사람이 읽고 바로 고칠 수 있어야 합니다
    assert 찍혀야_할_말 in str(caught.value)


def test_문제가_여러_개면_한_번에_다_알려준다():
    """하나 고치고 다시 띄웠더니 또 걸리는 일을 막습니다."""
    settings = Settings(app_env="production", dev_header_auth=True,
                        secret_key=DEFAULT_SECRET_KEY, cors_origins="*")
    assert len(production_problems(settings)) == 3


def test_prod_라고_써도_운영으로_본다():
    assert Settings(app_env="prod").is_production
    assert Settings(app_env="PRODUCTION").is_production
    assert not Settings(app_env="dev").is_production


# --------------------------- 접속 정보 잠그기 ---------------------------


def test_잠그면_원래_값이_안_보인다():
    headers = {"Authorization": "Bearer 진짜비밀토큰"}
    sealed = crypto.seal(headers)

    assert crypto.is_sealed(sealed)
    assert "진짜비밀토큰" not in str(sealed)
    assert crypto.unseal(sealed) == headers


def test_빈_값은_그냥_둔다():
    assert crypto.seal({}) == {}
    assert crypto.seal(None) == {}
    assert crypto.unseal({}) == {}
    assert crypto.unseal(None) == {}


def test_잠그기_전에_저장된_옛_데이터도_그대로_읽힌다():
    """이 기능을 올리는 순간 기존 앱이 멈추면 안 됩니다."""
    legacy = {"Authorization": "Bearer 옛날값"}
    assert crypto.unseal(legacy) == legacy
    assert not crypto.is_sealed(legacy)


def test_열쇠가_바뀌면_사람이_읽을_수_있는_이유가_나온다():
    sealed = crypto.seal({"Authorization": "Bearer 비밀"})
    crypto._cipher.cache_clear()
    other = crypto._cipher("완전히-다른-열쇠-" + "y" * 30)

    with pytest.raises(crypto.SecretUnreadable) as caught:
        # 다른 열쇠로 잠근 값을 지금 열쇠로 풀어 보는 상황과 같습니다
        crypto.unseal({crypto.SEALED_KEY: other.encrypt(b'{"a":1}').decode()})
    assert "ENCRYPTION_KEY" in str(caught.value)

    assert crypto.unseal(sealed) == {"Authorization": "Bearer 비밀"}
