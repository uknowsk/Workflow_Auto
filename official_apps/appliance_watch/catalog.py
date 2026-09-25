"""대륙별 가전 제조사, 품목, 가격대 기준표.

여기 있는 값은 "처음 켰을 때의 기본값"입니다. 제조사 순위는 해마다 바뀌므로
화면(또는 set_region_makers 기능)에서 대륙별 탑 5를 고쳐 쓸 수 있고,
고친 값은 저장소에 남아 이 기본값보다 먼저 쓰입니다.

site 는 "이 대륙에서 그 회사 제품이 올라오는 공식 홈페이지 시작 주소"입니다.
틀렸거나 비어 있어도 괜찮습니다. 검색 API 를 붙여 두면 앱이 스스로 찾아 채웁니다.
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

# ── 대륙별 탑 5 (기본값) ──────────────────────────────────────────────────
# 판매 점유율 기준의 대략적인 순서입니다. 회사 기준이 따로 있으면 화면에서 바꾸세요.
DEFAULT_MAKERS: dict[str, list[dict]] = {
    "north_america": [
        {"name": "Whirlpool", "site": "https://www.whirlpool.com"},
        {"name": "GE Appliances", "site": "https://www.geappliances.com"},
        {"name": "Samsung", "site": "https://www.samsung.com/us"},
        {"name": "LG", "site": "https://www.lg.com/us"},
        {"name": "Frigidaire (Electrolux)", "site": "https://www.frigidaire.com"},
    ],
    "europe": [
        {"name": "Bosch (BSH)", "site": "https://www.bosch-home.co.uk"},
        {"name": "Electrolux", "site": "https://www.electrolux.co.uk"},
        {"name": "Beko (Arçelik)", "site": "https://www.beko.co.uk"},
        {"name": "Miele", "site": "https://www.miele.co.uk"},
        {"name": "Samsung", "site": "https://www.samsung.com/uk"},
    ],
    "asia": [
        {"name": "Haier", "site": "https://www.haier.com"},
        {"name": "Midea", "site": "https://www.midea.com"},
        {"name": "Samsung", "site": "https://www.samsung.com/sec"},
        {"name": "LG", "site": "https://www.lge.co.kr"},
        {"name": "Panasonic", "site": "https://panasonic.jp"},
    ],
    "south_america": [
        {"name": "Brastemp (Whirlpool)", "site": "https://www.brastemp.com.br"},
        {"name": "Electrolux", "site": "https://www.electrolux.com.br"},
        {"name": "Samsung", "site": "https://www.samsung.com/br"},
        {"name": "LG", "site": "https://www.lg.com/br"},
        {"name": "Mabe", "site": "https://www.mabe.com.mx"},
    ],
    "oceania": [
        {"name": "Fisher & Paykel", "site": "https://www.fisherpaykel.com/au"},
        {"name": "Westinghouse (Electrolux)", "site": "https://www.westinghouse.com.au"},
        {"name": "Samsung", "site": "https://www.samsung.com/au"},
        {"name": "LG", "site": "https://www.lg.com/au"},
        {"name": "Bosch", "site": "https://www.bosch-home.com.au"},
    ],
}

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
