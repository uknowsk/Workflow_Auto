"""메일 어댑터 인터페이스.

사내 메일(Knox 메일)이 프로그램에 어떤 문을 열어 주는지 아직 확인되지 않았습니다.
그래서 "메일을 실제로 내보내는 부분"만 갈아끼울 수 있게 떼어 두었습니다.

  - 집/시험:  mock  (가짜 메일함. 실제로 보내지 않고 쌓아 두고 화면에서 봅니다)
  - 회사:     smtp  (사내 SMTP/IMAP. 값이 확인되면 이 어댑터만 채우면 됩니다)

앱의 나머지 부분(도구 목록, 회신 추적, 리마인드, 화면)은 어느 쪽이든 똑같이 돕니다.
"""


class MailAdapter:
    """메일을 보내고 회신을 확인하는 두 가지 일만 합니다."""

    name = "base"

    def send(self, to_addr: str, subject: str, body: str, headers: dict | None = None) -> str:
        """메일 한 통을 보냅니다. 메일 서버가 준 식별자를 돌려줍니다."""
        raise NotImplementedError

    def fetch_replies(self, mails: list[dict]) -> list[dict]:
        """받은 편지함을 보고 회신이 온 메일을 찾습니다.

        돌려주는 형식: [{"mail_id": 보낸메일id, "body": 회신 내용 요약}, ...]
        """
        raise NotImplementedError

    def describe(self) -> dict:
        """현재 설정 상태. 값(비밀번호 등)은 절대 담지 않고 '설정됨/안 됨'만 담습니다."""
        return {"adapter": self.name}
