"""어댑터 고르기. .env 의 MAIL_ADAPTER 한 줄로 바뀝니다.

  MAIL_ADAPTER=mock  -> 가짜 메일함 (기본값, 집에서 시험용)
  MAIL_ADAPTER=smtp  -> 사내 SMTP/IMAP (회사에서 값 확인 후)
"""
import os

from .base import MailAdapter
from .mock import MockAdapter
from .smtp_imap import SmtpImapAdapter

_ADAPTERS = {
    "mock": MockAdapter,
    "smtp": SmtpImapAdapter,
}


def get_adapter() -> MailAdapter:
    name = os.getenv("MAIL_ADAPTER", "mock").strip().lower()
    factory = _ADAPTERS.get(name)
    if factory is None:
        raise ValueError(
            f"MAIL_ADAPTER={name} 는 없는 값입니다. 쓸 수 있는 값: {', '.join(_ADAPTERS)}"
        )
    return factory()


__all__ = ["MailAdapter", "get_adapter"]
