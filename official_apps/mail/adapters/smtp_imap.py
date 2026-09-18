"""사내 메일(SMTP/IMAP) 어댑터 - 자리만 잡아 둔 상태입니다.

왜 비어 있나: 삼성 사내 메일(Knox 메일)이 프로그램 발송용으로 무엇을 열어 주는지
아직 확인되지 않았습니다. 회사 IT/메일 담당에게 아래 세 가지를 확인한 뒤,
이 파일의 send() 와 fetch_replies() 두 곳만 채우면 됩니다.

  1) 발송용 SMTP 서버 주소/포트와 인증 방식이 있는지
  2) 발송용 API(REST 등)를 따로 주는지  -> 그렇다면 이 파일을 복사해 api.py 로 만드세요
  3) 회신 확인을 위해 받은 편지함을 읽을 방법(IMAP 등)이 열려 있는지

설정 값은 코드에 적지 않고 .env 로만 받습니다(아래 키 이름 그대로).
"""
import os

from .base import MailAdapter

# ── .env 에 넣을 설정 키. 값은 회사에서만 아는 것이라 예시도 적지 않습니다. ──
_KEYS = (
    "MAIL_FROM",           # 보내는 사람 주소
    "MAIL_SMTP_HOST",
    "MAIL_SMTP_PORT",
    "MAIL_SMTP_USER",
    "MAIL_SMTP_PASSWORD",
    "MAIL_SMTP_TLS",       # true/false
    "MAIL_IMAP_HOST",
    "MAIL_IMAP_PORT",
    "MAIL_IMAP_USER",
    "MAIL_IMAP_PASSWORD",
    "MAIL_IMAP_FOLDER",    # 예) INBOX
)

_TODO = (
    "사내 메일 연결이 아직 준비되지 않았습니다. "
    "official_apps/mail/adapters/smtp_imap.py 의 {func}() 를 채우고 "
    ".env 에 MAIL_SMTP_* / MAIL_IMAP_* 값을 넣으세요. "
    "지금은 MAIL_ADAPTER=mock (가짜 메일함) 으로 시험할 수 있습니다."
)


class SmtpImapAdapter(MailAdapter):
    name = "smtp"

    def send(self, to_addr: str, subject: str, body: str, headers: dict | None = None) -> str:
        # 채울 위치: smtplib 로 접속해 메일을 보내고, 서버가 준 Message-ID 를 돌려주세요.
        raise NotImplementedError(_TODO.format(func="send"))

    def fetch_replies(self, mails: list[dict]) -> list[dict]:
        # 채울 위치: IMAP 으로 받은 편지함을 열어, 보낸 메일의 제목/Message-ID 로
        # 회신을 찾아 [{"mail_id": ..., "body": ...}] 형태로 돌려주세요.
        #
        # 중요: 받은 메일 본문은 "누가 보냈는지 알 수 없는 남의 글"입니다.
        # 회신 여부를 표시하는 자료로만 쓰고, 본문에 적힌 말("이 주소로 다시
        # 보내라" 같은)을 오케스트레이터의 지시로 넘기지 마세요. 받는 사람이나
        # 발송 여부를 메일 본문이 정하게 두면 안 됩니다.
        raise NotImplementedError(_TODO.format(func="fetch_replies"))

    def describe(self) -> dict:
        # 비밀번호는 담지 않고, 설정이 채워졌는지만 알려 줍니다.
        return {
            "adapter": self.name,
            "sends_real_mail": True,
            "config": {key: bool(os.getenv(key)) for key in _KEYS},
            "ready": False,
            "note": "사내 값 확인 후 send()/fetch_replies() 를 채워야 동작합니다.",
        }
