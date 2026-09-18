"""예약 시각 계산 테스트.

"매일 09시"나 "기한 하루 전"이 실제로 언제인지 계산하는 부분입니다.
한 시간만 어긋나도 리마인드가 엉뚱한 때 나가므로 여기를 못 박아 둡니다.
기준 시각은 전부 UTC 이고, 사내 표준시는 한국(UTC+9)으로 두었습니다.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.models import Schedule, ScheduleTrigger
from app.scheduler import service as scheduler

# 2026-09-18 00:00 UTC = 한국시간 2026-09-18(금) 09:00
NOW = datetime(2026, 9, 18, 0, 0, tzinfo=timezone.utc)


def local(moment: datetime) -> str:
    return scheduler.to_local(moment).strftime("%Y-%m-%d %H:%M")


def test_매일_정해진_시각은_다음날_같은_시각():
    row = Schedule(user_id="E1", title="매일 9시",
                   trigger=ScheduleTrigger.daily, at_time="09:00")
    # 지금이 마침 09:00 이므로 오늘은 지났고 내일이 다음 차례입니다.
    assert local(scheduler.compute_next_run(row, NOW)) == "2026-09-19 09:00"


def test_매일_예약은_아직_안_지난_시각이면_오늘():
    row = Schedule(user_id="E1", title="매일 18시",
                   trigger=ScheduleTrigger.daily, at_time="18:00")
    assert local(scheduler.compute_next_run(row, NOW)) == "2026-09-18 18:00"


def test_요일을_고르면_그_요일까지_건너뜁니다():
    # 2026-09-18 은 금요일. 월(0)/수(2)만 고르면 다음은 월요일 9/21.
    row = Schedule(user_id="E1", title="월수 08시", trigger=ScheduleTrigger.daily,
                   at_time="08:00", weekdays=[0, 2])
    assert local(scheduler.compute_next_run(row, NOW)) == "2026-09-21 08:00"


def test_기한_하루_전에_미리_실행():
    deadline = datetime(2026, 9, 25, 9, 0, tzinfo=timezone.utc)
    row = Schedule(user_id="E1", title="회신기한 리마인드",
                   trigger=ScheduleTrigger.once, run_at=deadline, lead_minutes=1440)
    assert scheduler.compute_next_run(row, NOW) == deadline - timedelta(days=1)


def test_이미_지난_시각이면_지금_바로():
    """기한이 코앞이라 '하루 전'이 이미 지났어도 알림은 나가야 합니다."""
    row = Schedule(user_id="E1", title="늦은 리마인드", trigger=ScheduleTrigger.once,
                   run_at=NOW + timedelta(hours=2), lead_minutes=1440)
    assert NOW < scheduler.compute_next_run(row, NOW) < NOW + timedelta(minutes=1)


def test_한_번짜리는_실행하고_나면_끝():
    row = Schedule(user_id="E1", title="한 번", trigger=ScheduleTrigger.once,
                   run_at=NOW + timedelta(days=1), run_count=1)
    assert scheduler.compute_next_run(row, NOW) is None


def test_시각을_안_정한_한_번짜리는_돌지_않습니다():
    row = Schedule(user_id="E1", title="빈 예약", trigger=ScheduleTrigger.once)
    assert scheduler.compute_next_run(row, NOW) is None


@pytest.mark.parametrize(
    "minutes,expected",
    [(30, 30), (60, 60), (1, 5)],  # 1분은 최소 간격(5분)으로 올라갑니다
)
def test_반복_간격(minutes, expected):
    row = Schedule(user_id="E1", title="반복", trigger=ScheduleTrigger.interval,
                   interval_minutes=minutes)
    assert scheduler.compute_next_run(row, NOW) == NOW + timedelta(minutes=expected)


def test_시각_형식이_이상하면_자정으로_봅니다():
    row = Schedule(user_id="E1", title="이상함",
                   trigger=ScheduleTrigger.daily, at_time="스물다섯시")
    assert local(scheduler.compute_next_run(row, NOW)) == "2026-09-19 00:00"


@pytest.mark.parametrize(
    "row,expected",
    [
        (Schedule(trigger=ScheduleTrigger.daily, at_time="09:00"), "매일 09:00"),
        (Schedule(trigger=ScheduleTrigger.daily, at_time="08:00", weekdays=[0, 2, 4]),
         "월 수 금 08:00"),
        (Schedule(trigger=ScheduleTrigger.interval, interval_minutes=30), "30분마다"),
        (Schedule(trigger=ScheduleTrigger.interval, interval_minutes=120), "2시간마다"),
    ],
)
def test_사람이_읽는_설명(row, expected):
    assert scheduler.describe(row) == expected


def test_기한_전_예약_설명():
    row = Schedule(trigger=ScheduleTrigger.once, lead_minutes=1440,
                   run_at=datetime(2026, 9, 25, 9, 0, tzinfo=timezone.utc))
    # 한국시간 9/25 18:00 기준 1일 전
    assert scheduler.describe(row) == "2026-09-25 18:00 기준 1일 전에 한 번"
