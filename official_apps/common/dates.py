"""날짜 문자열을 다루는 잔손질 모음. 여러 앱이 같은 규칙을 쓰도록 모아 두었습니다."""
from __future__ import annotations

from datetime import date, datetime, timedelta


def parse_date(value: str, fallback: date | None = None) -> date:
    """'2026-09-18' 같은 문자열을 날짜로. 비어 있거나 이상하면 fallback(기본 오늘)."""
    text = (value or "").strip()
    if not text:
        return fallback or date.today()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return fallback or date.today()


def days_between(start: str, end: str = "") -> int:
    """두 날짜 사이의 일수. end 를 비우면 오늘까지."""
    return (parse_date(end) - parse_date(start)).days


def week_range(any_day: str = "") -> tuple[date, date]:
    """그 날짜가 속한 주의 월요일과 금요일."""
    target = parse_date(any_day)
    monday = target - timedelta(days=target.weekday())
    return monday, monday + timedelta(days=4)
