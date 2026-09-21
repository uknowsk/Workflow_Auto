"""도구 모음 앱 - 계산기, 단위 변환, 세계 시계, 날짜 계산.

업무 중에 자주 찾게 되는 잔도구들입니다. 저장하는 것이 없어 가볍고,
다른 앱의 결과를 받아 계산만 해 주는 용도로도 자주 불립니다.
예) "미국 지사와 화요일 오전에 회의하려면 우리 시간 몇 시야?"

실행:  python -m toolbox.server   ->  http://localhost:9114/mcp
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
    port=int(os.getenv("PORT", "9114")),
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
# 도시 이름(한글·영문)이나 Asia/Seoul 같은 표준 이름으로 받습니다.
#
# 같은 목록이 화면 쪽(frontend/components/tools/city-zones.ts)에도 있습니다.
# 도커 빌드 범위가 서로 달라 파일 하나를 같이 쓰지는 못하니, 한쪽을 고치면 다른 쪽도
# 고쳐 주세요. tests/test_city_zones.py 가 두 목록이 어긋나면 알려 줍니다.
CITIES: list[tuple[str, str, str, str]] = [  # (도시, 영문 이름, 나라, 표준 시간대)
    # 한국
    ("서울", "Seoul", "한국", "Asia/Seoul"),
    ("수원", "Suwon", "한국", "Asia/Seoul"),
    ("기흥", "Giheung", "한국", "Asia/Seoul"),
    ("화성", "Hwaseong", "한국", "Asia/Seoul"),
    ("평택", "Pyeongtaek", "한국", "Asia/Seoul"),
    ("천안", "Cheonan", "한국", "Asia/Seoul"),
    ("아산", "Asan", "한국", "Asia/Seoul"),
    ("구미", "Gumi", "한국", "Asia/Seoul"),
    ("광주", "Gwangju", "한국", "Asia/Seoul"),
    ("대전", "Daejeon", "한국", "Asia/Seoul"),
    ("대구", "Daegu", "한국", "Asia/Seoul"),
    ("부산", "Busan", "한국", "Asia/Seoul"),
    ("제주", "Jeju", "한국", "Asia/Seoul"),
    # 일본
    ("도쿄", "Tokyo", "일본", "Asia/Tokyo"),
    ("오사카", "Osaka", "일본", "Asia/Tokyo"),
    ("나고야", "Nagoya", "일본", "Asia/Tokyo"),
    ("요코하마", "Yokohama", "일본", "Asia/Tokyo"),
    ("후쿠오카", "Fukuoka", "일본", "Asia/Tokyo"),
    ("삿포로", "Sapporo", "일본", "Asia/Tokyo"),
    # 중국·대만·홍콩
    ("베이징", "Beijing", "중국", "Asia/Shanghai"),
    ("상하이", "Shanghai", "중국", "Asia/Shanghai"),
    ("시안", "Xian", "중국", "Asia/Shanghai"),
    ("톈진", "Tianjin", "중국", "Asia/Shanghai"),
    ("쑤저우", "Suzhou", "중국", "Asia/Shanghai"),
    ("선전", "Shenzhen", "중국", "Asia/Shanghai"),
    ("광저우", "Guangzhou", "중국", "Asia/Shanghai"),
    ("칭다오", "Qingdao", "중국", "Asia/Shanghai"),
    ("청두", "Chengdu", "중국", "Asia/Shanghai"),
    ("홍콩", "Hong Kong", "홍콩", "Asia/Hong_Kong"),
    ("타이베이", "Taipei", "대만", "Asia/Taipei"),
    ("신주", "Hsinchu", "대만", "Asia/Taipei"),
    # 동남아시아
    ("호치민", "Ho Chi Minh City", "베트남", "Asia/Ho_Chi_Minh"),
    ("하노이", "Hanoi", "베트남", "Asia/Ho_Chi_Minh"),
    ("박닌", "Bac Ninh", "베트남", "Asia/Ho_Chi_Minh"),
    ("타이응우옌", "Thai Nguyen", "베트남", "Asia/Ho_Chi_Minh"),
    ("방콕", "Bangkok", "태국", "Asia/Bangkok"),
    ("싱가포르", "Singapore", "싱가포르", "Asia/Singapore"),
    ("쿠알라룸푸르", "Kuala Lumpur", "말레이시아", "Asia/Kuala_Lumpur"),
    ("자카르타", "Jakarta", "인도네시아", "Asia/Jakarta"),
    ("마닐라", "Manila", "필리핀", "Asia/Manila"),
    ("프놈펜", "Phnom Penh", "캄보디아", "Asia/Phnom_Penh"),
    ("양곤", "Yangon", "미얀마", "Asia/Yangon"),
    # 남아시아
    ("델리", "Delhi", "인도", "Asia/Kolkata"),
    ("노이다", "Noida", "인도", "Asia/Kolkata"),
    ("구르가온", "Gurgaon", "인도", "Asia/Kolkata"),
    ("벵갈루루", "Bengaluru", "인도", "Asia/Kolkata"),
    ("첸나이", "Chennai", "인도", "Asia/Kolkata"),
    ("뭄바이", "Mumbai", "인도", "Asia/Kolkata"),
    ("하이데라바드", "Hyderabad", "인도", "Asia/Kolkata"),
    ("콜카타", "Kolkata", "인도", "Asia/Kolkata"),
    ("다카", "Dhaka", "방글라데시", "Asia/Dhaka"),
    ("콜롬보", "Colombo", "스리랑카", "Asia/Colombo"),
    ("카라치", "Karachi", "파키스탄", "Asia/Karachi"),
    ("이슬라마바드", "Islamabad", "파키스탄", "Asia/Karachi"),
    # 중앙아시아·러시아
    ("타슈켄트", "Tashkent", "우즈베키스탄", "Asia/Tashkent"),
    ("알마티", "Almaty", "카자흐스탄", "Asia/Almaty"),
    ("블라디보스토크", "Vladivostok", "러시아", "Asia/Vladivostok"),
    ("노보시비르스크", "Novosibirsk", "러시아", "Asia/Novosibirsk"),
    ("모스크바", "Moscow", "러시아", "Europe/Moscow"),
    ("상트페테르부르크", "Saint Petersburg", "러시아", "Europe/Moscow"),
    # 중동·아프리카
    ("두바이", "Dubai", "아랍에미리트", "Asia/Dubai"),
    ("아부다비", "Abu Dhabi", "아랍에미리트", "Asia/Dubai"),
    ("도하", "Doha", "카타르", "Asia/Qatar"),
    ("리야드", "Riyadh", "사우디아라비아", "Asia/Riyadh"),
    ("제다", "Jeddah", "사우디아라비아", "Asia/Riyadh"),
    ("쿠웨이트", "Kuwait City", "쿠웨이트", "Asia/Kuwait"),
    ("테헤란", "Tehran", "이란", "Asia/Tehran"),
    ("텔아비브", "Tel Aviv", "이스라엘", "Asia/Jerusalem"),
    ("이스탄불", "Istanbul", "튀르키예", "Europe/Istanbul"),
    ("카이로", "Cairo", "이집트", "Africa/Cairo"),
    ("나이로비", "Nairobi", "케냐", "Africa/Nairobi"),
    ("라고스", "Lagos", "나이지리아", "Africa/Lagos"),
    ("요하네스버그", "Johannesburg", "남아프리카공화국", "Africa/Johannesburg"),
    ("카사블랑카", "Casablanca", "모로코", "Africa/Casablanca"),
    # 유럽
    ("런던", "London", "영국", "Europe/London"),
    ("더블린", "Dublin", "아일랜드", "Europe/Dublin"),
    ("리스본", "Lisbon", "포르투갈", "Europe/Lisbon"),
    ("파리", "Paris", "프랑스", "Europe/Paris"),
    ("프랑크푸르트", "Frankfurt", "독일", "Europe/Berlin"),
    ("베를린", "Berlin", "독일", "Europe/Berlin"),
    ("뮌헨", "Munich", "독일", "Europe/Berlin"),
    ("암스테르담", "Amsterdam", "네덜란드", "Europe/Amsterdam"),
    ("브뤼셀", "Brussels", "벨기에", "Europe/Brussels"),
    ("마드리드", "Madrid", "스페인", "Europe/Madrid"),
    ("바르셀로나", "Barcelona", "스페인", "Europe/Madrid"),
    ("로마", "Rome", "이탈리아", "Europe/Rome"),
    ("밀라노", "Milan", "이탈리아", "Europe/Rome"),
    ("취리히", "Zurich", "스위스", "Europe/Zurich"),
    ("제네바", "Geneva", "스위스", "Europe/Zurich"),
    ("빈", "Vienna", "오스트리아", "Europe/Vienna"),
    ("프라하", "Prague", "체코", "Europe/Prague"),
    ("부다페스트", "Budapest", "헝가리", "Europe/Budapest"),
    ("바르샤바", "Warsaw", "폴란드", "Europe/Warsaw"),
    ("스톡홀름", "Stockholm", "스웨덴", "Europe/Stockholm"),
    ("오슬로", "Oslo", "노르웨이", "Europe/Oslo"),
    ("코펜하겐", "Copenhagen", "덴마크", "Europe/Copenhagen"),
    ("헬싱키", "Helsinki", "핀란드", "Europe/Helsinki"),
    ("아테네", "Athens", "그리스", "Europe/Athens"),
    ("부쿠레슈티", "Bucharest", "루마니아", "Europe/Bucharest"),
    ("키이우", "Kyiv", "우크라이나", "Europe/Kyiv"),
    # 북미
    ("뉴욕", "New York", "미국", "America/New_York"),
    ("워싱턴", "Washington DC", "미국", "America/New_York"),
    ("보스턴", "Boston", "미국", "America/New_York"),
    ("애틀랜타", "Atlanta", "미국", "America/New_York"),
    ("마이애미", "Miami", "미국", "America/New_York"),
    ("디트로이트", "Detroit", "미국", "America/Detroit"),
    ("시카고", "Chicago", "미국", "America/Chicago"),
    ("오스틴", "Austin", "미국", "America/Chicago"),
    ("댈러스", "Dallas", "미국", "America/Chicago"),
    ("휴스턴", "Houston", "미국", "America/Chicago"),
    ("덴버", "Denver", "미국", "America/Denver"),
    ("솔트레이크시티", "Salt Lake City", "미국", "America/Denver"),
    ("피닉스", "Phoenix", "미국", "America/Phoenix"),
    ("시애틀", "Seattle", "미국", "America/Los_Angeles"),
    ("포틀랜드", "Portland", "미국", "America/Los_Angeles"),
    ("샌프란시스코", "San Francisco", "미국", "America/Los_Angeles"),
    ("산호세", "San Jose", "미국", "America/Los_Angeles"),
    ("로스앤젤레스", "Los Angeles", "미국", "America/Los_Angeles"),
    ("샌디에이고", "San Diego", "미국", "America/Los_Angeles"),
    ("라스베이거스", "Las Vegas", "미국", "America/Los_Angeles"),
    ("호놀룰루", "Honolulu", "미국", "Pacific/Honolulu"),
    ("앵커리지", "Anchorage", "미국", "America/Anchorage"),
    ("토론토", "Toronto", "캐나다", "America/Toronto"),
    ("몬트리올", "Montreal", "캐나다", "America/Toronto"),
    ("밴쿠버", "Vancouver", "캐나다", "America/Vancouver"),
    ("멕시코시티", "Mexico City", "멕시코", "America/Mexico_City"),
    ("몬테레이", "Monterrey", "멕시코", "America/Monterrey"),
    ("티후아나", "Tijuana", "멕시코", "America/Tijuana"),
    # 중남미
    ("파나마시티", "Panama City", "파나마", "America/Panama"),
    ("보고타", "Bogota", "콜롬비아", "America/Bogota"),
    ("리마", "Lima", "페루", "America/Lima"),
    ("산티아고", "Santiago", "칠레", "America/Santiago"),
    ("상파울루", "Sao Paulo", "브라질", "America/Sao_Paulo"),
    ("리우데자네이루", "Rio de Janeiro", "브라질", "America/Sao_Paulo"),
    ("마나우스", "Manaus", "브라질", "America/Manaus"),
    ("부에노스아이레스", "Buenos Aires", "아르헨티나", "America/Argentina/Buenos_Aires"),
    # 오세아니아
    ("시드니", "Sydney", "호주", "Australia/Sydney"),
    ("멜버른", "Melbourne", "호주", "Australia/Melbourne"),
    ("브리즈번", "Brisbane", "호주", "Australia/Brisbane"),
    ("퍼스", "Perth", "호주", "Australia/Perth"),
    ("애들레이드", "Adelaide", "호주", "Australia/Adelaide"),
    ("캔버라", "Canberra", "호주", "Australia/Sydney"),
    ("오클랜드", "Auckland", "뉴질랜드", "Pacific/Auckland"),
    ("웰링턴", "Wellington", "뉴질랜드", "Pacific/Auckland"),
    # 기준 시각
    ("협정세계시(UTC)", "UTC", "세계 표준", "UTC"),
]

# 한글 이름으로도 영문 이름으로도 찾히게 펼쳐 둡니다.
CITY_ZONES = {name: zone for name, _en, _country, zone in CITIES}
CITY_NAMES = [name for name, _en, _country, _zone in CITIES]
_EN_ZONES = {en.lower(): zone for _name, en, _country, zone in CITIES}


def _zone(city: str) -> ZoneInfo | None:
    name = city.strip()
    zone_name = CITY_ZONES.get(name) or _EN_ZONES.get(name.lower()) or name
    try:
        return ZoneInfo(zone_name)
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
        answer["hint"] = f"아는 도시: {', '.join(CITY_NAMES)} (영문 이름이나 Asia/Seoul 같은 표준 이름도 됩니다)"
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
