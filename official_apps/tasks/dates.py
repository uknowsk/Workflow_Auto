"""기한 문자열을 YYYY-MM-DD 로 맞춰 주는 작은 도구.

오케스트레이터(LLM)는 "9월 25일", "내일", "3일 뒤" 처럼 사람 말투로 기한을
넘길 수 있습니다. 그대로 저장하면 정렬도 비교도 안 되므로 여기서 한 형식으로
바꿉니다. 못 알아들으면 빈 문자열을 돌려주고, 앱은 "기한 없음"으로 다룹니다.
"""
import re
from datetime import date, timedelta

_YMD = re.compile(r"(\d{4})\D{1,2}(\d{1,2})\D{1,2}(\d{1,2})")
_MD = re.compile(r"(\d{1,2})\D{1,2}(\d{1,2})")
_AFTER_DAYS = re.compile(r"(\d+)\s*(일|영업일)")
_WEEKDAYS = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6}


def today() -> date:
    return date.today()


def parse_due(text: str) -> str:
    """사람이 적은 기한을 YYYY-MM-DD 로 바꿉니다. 모르면 빈 문자열."""
    raw = (text or "").strip()
    if not raw:
        return ""

    if raw in ("오늘", "금일"):
        return today().isoformat()
    if raw in ("내일", "명일"):
        return (today() + timedelta(days=1)).isoformat()
    if raw == "모레":
        return (today() + timedelta(days=2)).isoformat()
    if raw in ("어제", "작일"):
        return (today() - timedelta(days=1)).isoformat()

    found = _YMD.search(raw)
    if found:
        year, month, day = (int(x) for x in found.groups())
        return _safe(year, month, day)

    # "3일 뒤", "5영업일 내" 같은 표현 (영업일도 단순히 날수로 셉니다)
    if any(word in raw for word in ("뒤", "후", "내", "이내")):
        after = _AFTER_DAYS.search(raw)
        if after:
            return (today() + timedelta(days=int(after.group(1)))).isoformat()

    # "금요일까지", "다음주 월요일"
    for name, index in _WEEKDAYS.items():
        if f"{name}요일" in raw:
            ahead = (index - today().weekday()) % 7 or 7
            if "다음" in raw or "차주" in raw:
                ahead += 7 if ahead <= 7 else 0
            return (today() + timedelta(days=ahead)).isoformat()

    found = _MD.search(raw)
    if found:
        month, day = (int(x) for x in found.groups())
        guess = _safe(today().year, month, day)
        # 이미 지난 날짜면 내년으로 봅니다 (12월에 "1월 5일" 이라고 하면 내년)
        if guess and guess < today().isoformat() and (today().month - month) > 6:
            return _safe(today().year + 1, month, day)
        return guess

    return ""


def _safe(year: int, month: int, day: int) -> str:
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return ""


def days_left(due: str) -> int | None:
    """기한까지 남은 날. 지났으면 음수, 기한이 없으면 None."""
    if not due:
        return None
    try:
        return (date.fromisoformat(due) - today()).days
    except ValueError:
        return None
