"""세계 시계 도시 목록이 앱과 화면에서 어긋나지 않는지 봅니다.

도시 목록은 두 곳에 있습니다.
  · official_apps/toolbox/server.py     (오케스트레이터가 부르는 앱)
  · frontend/components/tools/city-zones.ts (도구 서랍 화면)
도커 빌드 범위가 서로 달라 파일 하나를 같이 쓰지 못해서, 대신 이 테스트가
한쪽만 고쳐 두면 바로 알려 줍니다.
"""
import re
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pytest

from toolbox import server as toolbox

CITY_ZONES_TS = Path(__file__).resolve().parents[2] / "frontend/components/tools/city-zones.ts"
ROW = re.compile(
    r'\{\s*name:\s*"([^"]+)",\s*en:\s*"([^"]+)",\s*country:\s*"([^"]+)",\s*zone:\s*"([^"]+)"\s*\}'
)


def _screen_cities() -> list[tuple[str, str, str, str]]:
    if not CITY_ZONES_TS.exists():
        # 앱만 따로 빌드한 컨테이너 안에서는 화면 쪽 파일이 없습니다.
        pytest.skip("화면 쪽 도시 목록 파일이 없는 곳에서 돌고 있습니다")
    return ROW.findall(CITY_ZONES_TS.read_text(encoding="utf-8"))


def test_앱과_화면의_도시_목록이_같다():
    assert _screen_cities() == toolbox.CITIES


def test_도시_이름이_겹치지_않는다():
    assert len(toolbox.CITY_NAMES) == len(set(toolbox.CITY_NAMES))


def test_모든_시간대가_진짜로_있는_이름이다():
    for name, _en, _country, zone in toolbox.CITIES:
        try:
            ZoneInfo(zone)
        except (ZoneInfoNotFoundError, ValueError):  # pragma: no cover
            pytest.fail(f"{name} 의 시간대 {zone} 를 찾을 수 없습니다")


def test_영문_이름으로도_시각을_찾는다():
    answer = toolbox.world_clock(["New York", "frankfurt", "Asia/Seoul"])
    assert "unknown" not in answer
    assert len(answer["clocks"]) == 3


def test_모르는_도시는_아는_도시를_알려준다():
    answer = toolbox.world_clock(["없는도시"])
    assert answer["unknown"] == ["없는도시"]
    assert "서울" in answer["hint"]
