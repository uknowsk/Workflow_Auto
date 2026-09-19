"""가짜 메일함 어댑터 (기본값).

실제로 메일을 내보내지 않습니다. 보낸 메일은 앱의 DB에 쌓이고 화면에서 볼 수
있습니다. 회신은 화면의 "회신 온 것으로 표시" 버튼이나 mark_replied 도구로
표시합니다. 덕분에 사내 메일 설정 없이도 "회의록 → 할 일 → 메일 → 리마인드"
전체 흐름을 집에서 그대로 검증할 수 있습니다.
"""
import uuid

from .base import MailAdapter


class MockAdapter(MailAdapter):
    name = "mock"

    def send(self, to_addr: str, subject: str, body: str, headers: dict | None = None) -> str:
        # 보낸 척만 합니다. 저장은 store.record_sent() 가 합니다.
        return f"mock-{uuid.uuid4().hex[:12]}"

    def fetch_replies(self, mails: list[dict]) -> list[dict]:
        # 가짜 메일함에는 받은 편지함이 없습니다. 회신 표시는 사람이 눌러서 합니다.
        return []

    def describe(self) -> dict:
        return {
            "adapter": self.name,
            "sends_real_mail": False,
            "note": "가짜 메일함입니다. 실제로 메일이 나가지 않습니다.",
        }
