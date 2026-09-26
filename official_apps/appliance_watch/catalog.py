"""가전 제조사(글로벌 탑 20), 품목, 가격대 기준표.

**대륙별 탑 5 → 글로벌 탑 20 으로 바꿨습니다.** 대륙 매출 순위로만 고르면
보쉬·미얼레·KitchenAid 처럼 특정 대륙 판매 5위 안에는 못 들어도 전 세계
적으로 영향력이 큰 브랜드가 조사 대상에서 통째로 빠지는 문제가 있었습니다.
그래서 이제는 "영향력 기준 글로벌 20개 브랜드" 하나의 순위표(GLOBAL_BRANDS)를
모든 대륙이 같이 쓰고, 대륙(REGIONS)은 그 브랜드를 "어느 홈페이지로 볼지"와
"어느 통화로 비교할지"를 고르는 용도로만 씁니다.

여기 있는 값은 "처음 켰을 때의 기본값"입니다. 화면(또는 set_region_makers
기능)에서 고쳐 쓸 수 있고, 고친 값은 저장소에 남아 이 기본값보다 먼저 쓰입니다.

site 는 "이 대륙에서 그 회사 제품이 올라오는 공식 홈페이지 시작 주소"입니다.
틀렸거나 비어 있어도 괜찮습니다. 화면에서 직접 채우거나, 검색 API 를 붙여
두면 앱이 스스로 찾아 채웁니다. (BRAND_SITES 의 주소는 사람이 직접 확인을
마쳤습니다 — 자세한 확인 상태는 BRAND_SITES 위 주석을 보세요.)
"""
from __future__ import annotations

import json
import os
import re

# ── 대륙 ────────────────────────────────────────────────────────────────
REGIONS: dict[str, dict] = {
    "north_america": {"label": "북아메리카", "currency": "USD"},
    "europe": {"label": "유럽", "currency": "EUR"},
    "asia": {"label": "아시아", "currency": "KRW"},
    "south_america": {"label": "남아메리카", "currency": "BRL"},
    "oceania": {"label": "오세아니아", "currency": "AUD"},
}

# ── 글로벌 탑 20 (영향력 기준, 기본값) ────────────────────────────────────
# 판매량·인지도·프리미엄 시장 영향력을 종합한 대략적인 순위입니다.
# tier 는 화면에 참고로 보여주는 분류일 뿐, 조사 여부에는 영향을 주지 않습니다.
#   글로벌 톱티어 = 여러 대륙에서 상위권 판매
#   프리미엄      = 판매량은 적어도 트렌드·스펙을 선도하는 고급 브랜드
#   지역 강세     = 특정 대륙에서 특히 강한 브랜드(대개 글로벌 브랜드의 지역 라인)
GLOBAL_BRANDS: list[dict] = [
    {"name": "Samsung", "tier": "글로벌 톱티어"},
    {"name": "LG", "tier": "글로벌 톱티어"},
    {"name": "Whirlpool", "tier": "글로벌 톱티어"},
    {"name": "GE Appliances", "tier": "글로벌 톱티어"},
    {"name": "Bosch (BSH)", "tier": "글로벌 톱티어"},
    {"name": "Electrolux", "tier": "글로벌 톱티어"},
    {"name": "Haier", "tier": "글로벌 톱티어"},
    {"name": "Midea", "tier": "글로벌 톱티어"},
    {"name": "Panasonic", "tier": "글로벌 톱티어"},
    {"name": "Hisense", "tier": "글로벌 톱티어"},
    {"name": "Miele", "tier": "프리미엄"},
    {"name": "KitchenAid", "tier": "프리미엄"},
    {"name": "AEG", "tier": "프리미엄"},
    {"name": "Viking", "tier": "프리미엄"},
    {"name": "Sub-Zero / Wolf", "tier": "프리미엄"},
    {"name": "Thermador (BSH)", "tier": "프리미엄"},
    {"name": "Fisher & Paykel (Haier)", "tier": "프리미엄"},
    {"name": "Frigidaire (Electrolux)", "tier": "지역 강세"},
    {"name": "Beko (Arçelik)", "tier": "지역 강세"},
    {"name": "Gorenje (Hisense)", "tier": "지역 강세"},
]

# ── 브랜드 × 대륙 → 공식 홈페이지 ─────────────────────────────────────────
# 비어 있으면(또는 그 대륙 키가 아예 없으면) 화면에서 채우거나 검색 API 가
# 스스로 찾습니다. 그동안은 "홈페이지를 모릅니다" 로 조용히 넘어가고 나머지
# 19개 브랜드는 그대로 조사됩니다 — 하나가 비어 있다고 전체가 막히지 않습니다.
#
# 확인 상태(2026-09-26): 개발 중 샌드박스가 whirlpool.com·geappliances.com 말고는
# 거의 다 막혀 있어서(위키백과·검색엔진까지) 직접 열어 본 건 Whirlpool, GE
# Appliances, Samsung(5개 지역), KitchenAid(.com), Frigidaire(.com) 뿐이었지만,
# 나머지(LG, Bosch, Electrolux, Haier, Midea, Panasonic, Hisense, Miele, AEG,
# Viking, Sub-Zero/Wolf, Thermador, Fisher&Paykel, Beko, Gorenje)도 사람이
# 직접 확인해서 전부 맞다고 확인해 줬습니다. KitchenAid 유럽만 아직 비어
# 있습니다(.co.uk 인지 .eu 인지 확인이 안 됨).
BRAND_SITES: dict[str, dict[str, str]] = {
    "Samsung": {
        "north_america": "https://www.samsung.com/us",
        "europe": "https://www.samsung.com/uk",
        "asia": "https://www.samsung.com/sec",
        "south_america": "https://www.samsung.com/br",
        "oceania": "https://www.samsung.com/au",
    },
    "LG": {
        "north_america": "https://www.lg.com/us",
        "europe": "https://www.lg.com/uk",
        "asia": "https://www.lge.co.kr",
        "south_america": "https://www.lg.com/br",
        "oceania": "https://www.lg.com/au",
    },
    "Whirlpool": {"north_america": "https://www.whirlpool.com"},
    "GE Appliances": {"north_america": "https://www.geappliances.com"},
    "Bosch (BSH)": {
        "north_america": "https://www.bosch-home.com/us",
        "europe": "https://www.bosch-home.co.uk",
        "oceania": "https://www.bosch-home.com.au",
    },
    "Electrolux": {
        "europe": "https://www.electrolux.co.uk",
        "south_america": "https://www.electrolux.com.br",
    },
    "Haier": {"asia": "https://www.haier.com"},
    "Midea": {"asia": "https://www.midea.com"},
    "Panasonic": {
        "asia": "https://panasonic.jp",
        # 정확한 하위 경로(예: /uk/consumer.html)는 자주 바뀌어서 실제로 켜기
        # 전에 확인이 필요합니다. 홈페이지 최상단 주소만 주면 discover.py 가
        # 메뉴를 따라가며 스스로 하위 품목 페이지를 찾습니다.
        "europe": "https://www.panasonic.com/uk",
    },
    "Hisense": {"north_america": "https://www.hisense-usa.com"},
    "Miele": {
        "north_america": "https://www.mieleusa.com",
        "europe": "https://www.miele.co.uk",
    },
    "KitchenAid": {
        "north_america": "https://www.kitchenaid.com",
        # 유럽은 kitchenaid.co.uk 인지 kitchenaid.eu(국가 선택형)인지 확인이 안 돼서
        # 비워 뒀습니다. 화면에서 채우거나 SEARCH_PROVIDER 가 찾게 하세요.
    },
    "AEG": {"europe": "https://www.aeg.co.uk"},
    "Viking": {"north_america": "https://www.vikingrange.com"},
    "Sub-Zero / Wolf": {"north_america": "https://www.subzero-wolf.com"},
    "Thermador (BSH)": {"north_america": "https://www.thermador.com"},
    "Fisher & Paykel (Haier)": {
        "oceania": "https://www.fisherpaykel.com/au",
        "north_america": "https://www.fisherpaykel.com/us",
    },
    "Frigidaire (Electrolux)": {"north_america": "https://www.frigidaire.com"},
    "Beko (Arçelik)": {"europe": "https://www.beko.co.uk"},
    "Gorenje (Hisense)": {"europe": "https://www.gorenje.com"},
}


def global_brands() -> list[dict]:
    """영향력 기준 글로벌 20개 브랜드 순위표(이름 + tier)."""
    return [dict(b) for b in GLOBAL_BRANDS]


def brand_site(name: str, region: str) -> str:
    return BRAND_SITES.get(name, {}).get(region, "")


def default_region_makers(region: str) -> list[dict]:
    """이 대륙에서 기본으로 살펴볼 회사 목록 — 글로벌 20개 브랜드 전부입니다.

    이 대륙에 홈페이지 주소를 아는 브랜드는 그 주소로, 모르는 브랜드는 주소
    없이 올려 둡니다(화면에서 채우거나 검색 API 가 찾을 수 있게). "그 대륙
    판매 5위 안에 든 회사만" 이 아니라 20개 전부를 후보로 두는 게 핵심입니다.
    """
    return [{"name": b["name"], "site": brand_site(b["name"], region)} for b in GLOBAL_BRANDS]

# ── 품목 ────────────────────────────────────────────────────────────────
# keywords 는 주소(URL)나 링크 글자에 이 말이 들어 있으면 그 품목으로 봅니다.
# 여러 나라 사이트를 돌아야 하므로 영어 말고도 현지어를 같이 적어 둡니다.
# bands 는 가격대를 나누는 경계(달러). [a, b, c] 면
#   a 미만 = 보급형, a~b = 중급형, b~c = 프리미엄, c 이상 = 최고급
CATEGORIES: dict[str, dict] = {
    "cooking": {
        "label": "조리기기",
        "keywords": [
            "range", "oven", "cooktop", "hob", "microwave", "stove", "cooker",
            "backofen", "kochfeld", "fours", "cuisson", "horno", "fogao", "fogão", "forno",
            "cocina", "오븐", "레인지", "쿡탑", "전자레인지", "인덕션", "炉", "烤箱",
        ],
        "bands": [800, 1800, 3500],
    },
    "refrigerator": {
        "label": "냉장고",
        "keywords": [
            "refrigerator", "fridge", "freezer", "kuhlschrank", "kühlschrank",
            "refrigerateur", "réfrigérateur", "refrigerador", "geladeira", "냉장고", "冰箱",
        ],
        "bands": [1200, 2500, 4500],
    },
    "laundry": {
        "label": "세탁기·건조기",
        "keywords": [
            "washer", "washing", "dryer", "laundry", "waschmaschine", "trockner",
            "lave-linge", "lavadora", "secadora", "lavadora-de-roupas", "세탁기",
            "건조기", "洗衣机",
        ],
        "bands": [700, 1400, 2500],
    },
    "dishwasher": {
        "label": "식기세척기",
        "keywords": [
            "dishwasher", "geschirrspuler", "geschirrspüler", "lave-vaisselle",
            "lavavajillas", "lava-louca", "lava-louça", "식기세척기", "洗碗机",
        ],
        "bands": [600, 1100, 1800],
    },
    "air": {
        "label": "에어컨·공기청정",
        "keywords": [
            "air-conditioner", "air conditioner", "airconditioner", "aircon",
            "purifier", "dehumidifier", "klimaanlage", "climatiseur",
            "aire-acondicionado", "ar-condicionado", "에어컨", "공기청정기", "空调",
        ],
        "bands": [500, 1200, 2500],
    },
    "vacuum": {
        "label": "청소기",
        "keywords": [
            "vacuum", "robot-vacuum", "staubsauger", "aspirateur", "aspiradora",
            "aspirador", "청소기", "吸尘器",
        ],
        "bands": [250, 600, 1000],
    },
}

BAND_LABELS = ["보급형", "중급형", "프리미엄", "최고급"]

# ── 환율 (1 달러에 얼마) ────────────────────────────────────────────────
# 가격대를 대륙끼리 비교하려고 전부 달러로 바꿉니다. 대략값이므로
# 정확한 값이 필요하면 .env 에 FX_RATES_JSON='{"EUR":0.92,...}' 로 덮어쓰세요.
DEFAULT_FX_PER_USD: dict[str, float] = {
    "USD": 1.0,
    "CAD": 1.37,
    "MXN": 18.5,
    "EUR": 0.92,
    "GBP": 0.78,
    "CHF": 0.88,
    "SEK": 10.5,
    "PLN": 3.95,
    "KRW": 1380.0,
    "JPY": 148.0,
    "CNY": 7.2,
    "INR": 84.0,
    "BRL": 5.5,
    "ARS": 950.0,
    "CLP": 930.0,
    "COP": 4100.0,
    "AUD": 1.5,
    "NZD": 1.65,
}

# 가격에 붙은 기호로 통화를 짐작할 때 씁니다. 모호한 "$" 는 대륙 통화로 봅니다.
SYMBOL_CURRENCY = {
    "€": "EUR",
    "£": "GBP",
    "₩": "KRW",
    "¥": "JPY",
    "R$": "BRL",
    "A$": "AUD",
    "AU$": "AUD",
    "NZ$": "NZD",
    "C$": "CAD",
    "CA$": "CAD",
    "US$": "USD",
    "원": "KRW",
}


def fx_rates() -> dict[str, float]:
    rates = dict(DEFAULT_FX_PER_USD)
    raw = os.getenv("FX_RATES_JSON", "").strip()
    if raw:
        try:
            rates.update({k.upper(): float(v) for k, v in json.loads(raw).items()})
        except (ValueError, AttributeError):
            pass
    return rates


def to_usd(amount: float | None, currency: str) -> float | None:
    if amount is None:
        return None
    rate = fx_rates().get((currency or "USD").upper())
    if not rate:
        return None
    return round(amount / rate, 2)


def band_of(price_usd: float | None, category: str) -> str:
    """달러 가격을 품목별 경계에 맞춰 가격대 이름으로 바꿉니다."""
    if price_usd is None:
        return "가격 미확인"
    edges = CATEGORIES.get(category, {}).get("bands", [800, 1800, 3500])
    for edge, label in zip(edges, BAND_LABELS):
        if price_usd < edge:
            return label
    return BAND_LABELS[-1]


def band_ranges(category: str) -> list[dict]:
    """화면에 '보급형 $0~800' 처럼 보여 줄 가격대 구간."""
    edges = CATEGORIES.get(category, {}).get("bands", [800, 1800, 3500])
    lows = [0, *edges]
    highs = [*edges, None]
    return [
        {"label": label, "min_usd": low, "max_usd": high}
        for label, low, high in zip(BAND_LABELS, lows, highs)
    ]


def _has_word(text: str, word: str) -> bool:
    # 영어·유럽어 낱말은 낱말 단위로만 맞춥니다("range" 가 "orange" 에 걸리지 않게).
    # 한글·한자는 띄어쓰기 없이 붙어 쓰므로 그냥 들어 있으면 맞은 것으로 봅니다.
    if word.isascii():
        pattern = r"(?<![a-z])" + re.escape(word).replace(r"\ ", "[-_ ]") + r"s?(?![a-z])"
        return re.search(pattern, text) is not None
    return word in text


def keyword_hit(text: str, category: str) -> bool:
    lowered = text.lower()
    return any(_has_word(lowered, w) for w in CATEGORIES.get(category, {}).get("keywords", []))


def category_of(text: str) -> str:
    """주소나 글자에서 어느 품목인지 짐작합니다. 모르면 빈 문자열."""
    for key in CATEGORIES:
        if keyword_hit(text, key):
            return key
    return ""
