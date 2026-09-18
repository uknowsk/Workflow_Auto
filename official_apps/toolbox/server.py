"""도구 모음 앱 - 계산기, 단위 변환, 세계 시계, 날짜 계산.

업무 중에 자주 찾게 되는 잔도구들입니다. 저장하는 것이 없어 가볍고,
다른 앱의 결과를 받아 계산만 해 주는 용도로도 자주 불립니다.
예) "미국 지사와 화요일 오전에 회의하려면 우리 시간 몇 시야?"

실행:  python -m toolbox.server   ->  http://localhost:9104/mcp
"""
import ast
import operator
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mcp.server.fastmcp import FastMCP

from common.dates import parse_date

mcp = FastMCP(
    "도구 모음 (계산기·단위변환·세계시계)",
    instructions="계산, 단위 변환, 도시별 현재 시각, 날짜/기한 계산을 해 줍니다.",
    host=os.getenv("HOST", "0.0.0.0"),
    port=int(os.getenv("PORT", "9104")),
)

# ── 계산기 ──────────────────────────────────────────────────────────────
# eval() 은 쓰지 않습니다. 사용자가 넣은 글자가 그대로 실행되면 위험하니,
# 수식을 뜯어보고 사칙연산 같은 안전한 것만 계산합니다.
_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_eval(node.operand))
    raise ValueError("계산할 수 없는 식입니다. 숫자와 + - * / % ** ( ) 만 쓸 수 있습니다.")


@mcp.tool()
def calculate(expression: str) -> dict:
    """수식을 계산합니다. 숫자와 + - * / % ** 괄호를 쓸 수 있습니다.

    Args:
        expression: 계산할 식. 예) (1250000 * 1.1) / 12
    """
    cleaned = expression.replace(",", "").replace("×", "*").replace("÷", "/").strip()
    try:
        value = _eval(ast.parse(cleaned, mode="eval").body)
    except ZeroDivisionError:
        return {"ok": False, "error": "0 으로 나눌 수 없습니다."}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    rounded = round(value, 6)
    return {
        "ok": True,
        "expression": cleaned,
        "result": rounded,
        "formatted": f"{rounded:,}",
    }


# ── 단위 변환 ───────────────────────────────────────────────────────────
# 각 단위를 '기준 단위 몇 개인가'로 적어 두고, 나눗셈 한 번으로 변환합니다.
UNITS = {
    "길이": {"mm": 0.001, "cm": 0.01, "m": 1.0, "km": 1000.0, "inch": 0.0254,
             "ft": 0.3048, "yard": 0.9144, "mile": 1609.344, "자": 0.303},
    "무게": {"mg": 0.000001, "g": 0.001, "kg": 1.0, "t": 1000.0,
             "oz": 0.0283495, "lb": 0.453592, "근": 0.6, "돈": 0.00375},
    "넓이": {"m2": 1.0, "cm2": 0.0001, "km2": 1000000.0, "평": 3.305785, "ha": 10000.0,
             "에이커": 4046.86},
    "부피": {"ml": 0.001, "l": 1.0, "m3": 1000.0, "컵": 0.2, "말": 18.0, "갤런": 3.78541},
    "시간": {"초": 1.0, "분": 60.0, "시간": 3600.0, "일": 86400.0, "주": 604800.0},
    "데이터": {"b": 1.0, "kb": 1024.0, "mb": 1048576.0, "gb": 1073741824.0,
               "tb": 1099511627776.0},
}
TEMPERATURE = {"c", "f", "k", "섭씨", "화씨"}


def _to_celsius(value: float, unit: str) -> float:
    if unit in ("f", "화씨"):
        return (value - 32) * 5 / 9
    if unit == "k":
        return value - 273.15
    return value


def _from_celsius(value: float, unit: str) -> float:
    if unit in ("f", "화씨"):
        return value * 9 / 5 + 32
    if unit == "k":
        return value + 273.15
    return value


@mcp.tool()
def convert_unit(value: float, from_unit: str, to_unit: str) -> dict:
    """단위를 바꿔 줍니다. 길이, 무게, 넓이, 부피, 시간, 데이터, 온도를 다룹니다.

    Args:
        value: 바꿀 값. 예) 25.4
        from_unit: 지금 단위. 예) mm, kg, 평, gb, c
        to_unit: 바꿀 단위. 예) inch, lb, m2, mb, f
    """
    source, target = from_unit.strip().lower(), to_unit.strip().lower()

    if source in TEMPERATURE and target in TEMPERATURE:
        result = _from_celsius(_to_celsius(value, source), target)
        return {"ok": True, "category": "온도", "result": round(result, 4),
                "formatted": f"{value}{from_unit} = {round(result, 4)}{to_unit}"}

    for category, table in UNITS.items():
        if source in table and target in table:
            result = value * table[source] / table[target]
            return {"ok": True, "category": category, "result": round(result, 6),
                    "formatted": f"{value}{from_unit} = {round(result, 6):,}{to_unit}"}

    known = {name: sorted(table) for name, table in UNITS.items()}
    known["온도"] = sorted(TEMPERATURE)
    return {"ok": False, "error": f"{from_unit} → {to_unit} 은 아직 못 바꿉니다.", "supported": known}


# ── 세계 시계 ───────────────────────────────────────────────────────────
# 사내에서 자주 쓰는 도시만 이름으로 받고, 나머지는 Asia/Seoul 같은 표준 이름으로 받습니다.
CITY_ZONES = {
    "서울": "Asia/Seoul", "수원": "Asia/Seoul", "도쿄": "Asia/Tokyo", "베이징": "Asia/Shanghai",
    "상하이": "Asia/Shanghai", "시안": "Asia/Shanghai", "호치민": "Asia/Ho_Chi_Minh",
    "하노이": "Asia/Ho_Chi_Minh", "델리": "Asia/Kolkata", "벵갈루루": "Asia/Kolkata",
    "두바이": "Asia/Dubai", "런던": "Europe/London", "파리": "Europe/Paris",
    "프랑크푸르트": "Europe/Berlin", "바르샤바": "Europe/Warsaw", "모스크바": "Europe/Moscow",
    "뉴욕": "America/New_York", "오스틴": "America/Chicago", "산호세": "America/Los_Angeles",
    "샌프란시스코": "America/Los_Angeles", "상파울루": "America/Sao_Paulo",
    "시드니": "Australia/Sydney",
}


def _zone(city: str) -> ZoneInfo | None:
    name = city.strip()
    try:
        return ZoneInfo(CITY_ZONES.get(name, name))
    except (ZoneInfoNotFoundError, ValueError):
        return None


@mcp.tool()
def world_clock(cities: list[str]) -> dict:
    """도시들의 현재 시각을 한 번에 알려줍니다.

    Args:
        cities: 도시 이름 목록. 예) ["서울", "뉴욕", "프랑크푸르트"]
    """
    rows, unknown = [], []
    for city in cities or ["서울"]:
        zone = _zone(city)
        if zone is None:
            unknown.append(city)
            continue
        now = datetime.now(zone)
        rows.append({
            "city": city,
            "time": now.strftime("%Y-%m-%d %H:%M"),
            "weekday": "월화수목금토일"[now.weekday()],
            "utc_offset": now.strftime("%z"),
            "business_hours": 9 <= now.hour < 18 and now.weekday() < 5,
        })
    answer = {"clocks": rows}
    if unknown:
        answer["unknown"] = unknown
        answer["hint"] = f"아는 도시: {', '.join(sorted(CITY_ZONES))} (또는 Asia/Seoul 같은 표준 이름)"
    return answer


@mcp.tool()
def time_in(city: str, source_city: str = "서울", at_time: str = "") -> dict:
    """우리 시간 기준 어떤 시각이 다른 도시에서는 몇 시인지 알려줍니다.

    해외 지사와 회의 시간을 잡을 때 씁니다.

    Args:
        city: 궁금한 도시. 예) 뉴욕
        source_city: 기준 도시. 기본 서울
        at_time: 기준 도시의 시각. 예) 2026-09-21 14:00. 비우면 지금
    """
    source_zone, target_zone = _zone(source_city), _zone(city)
    if source_zone is None or target_zone is None:
        return {"ok": False, "error": f"모르는 도시입니다: {source_city if source_zone is None else city}"}

    if at_time.strip():
        try:
            moment = datetime.strptime(at_time.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=source_zone)
        except ValueError:
            return {"ok": False, "error": "시각은 '2026-09-21 14:00' 모양으로 적어 주세요."}
    else:
        moment = datetime.now(source_zone)

    there = moment.astimezone(target_zone)
    return {
        "ok": True,
        "source": f"{source_city} {moment.strftime('%Y-%m-%d %H:%M')}",
        "target": f"{city} {there.strftime('%Y-%m-%d %H:%M')}",
        "business_hours": 9 <= there.hour < 18 and there.weekday() < 5,
    }


# ── 날짜 계산 ───────────────────────────────────────────────────────────
@mcp.tool()
def date_difference(start_date: str, end_date: str = "") -> dict:
    """두 날짜 사이가 며칠인지, 근무일로는 며칠인지 알려줍니다.

    Args:
        start_date: 시작일. 예) 2026-09-01
        end_date: 종료일. 비우면 오늘. 예) 2026-09-30
    """
    start, end = parse_date(start_date), parse_date(end_date)
    days = (end - start).days
    step = 1 if days >= 0 else -1
    workdays = sum(
        1
        for offset in range(0, days, step)
        if (start + timedelta(days=offset)).weekday() < 5
    )
    return {
        "start": str(start),
        "end": str(end),
        "days": days,
        "workdays": workdays * (1 if days >= 0 else -1),
        "weeks": round(days / 7, 1),
    }


@mcp.tool()
def add_workdays(start_date: str, workdays: int) -> dict:
    """어떤 날짜에서 근무일(주말 제외) 며칠 뒤가 언제인지 알려줍니다.

    "회신 기한 3 근무일" 같은 기한을 잡을 때 씁니다. 공휴일은 반영하지 않습니다.

    Args:
        start_date: 기준일. 예) 2026-09-18
        workdays: 더할 근무일 수. 예) 3
    """
    current = parse_date(start_date)
    step = 1 if workdays >= 0 else -1
    remaining = abs(workdays)
    while remaining:
        current += timedelta(days=step)
        if current.weekday() < 5:
            remaining -= 1
    return {
        "start": start_date or "오늘",
        "workdays": workdays,
        "result": str(current),
        "weekday": "월화수목금토일"[current.weekday()],
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
