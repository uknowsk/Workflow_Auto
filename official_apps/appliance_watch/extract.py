"""제품 상세 페이지 한 장에서 이름·모델·가격·스펙·특징을 뽑아냅니다.

대부분의 쇼핑 페이지는 검색엔진을 위해 페이지 안에 "기계가 읽는 제품 카드"
(JSON-LD, schema.org/Product)를 숨겨 둡니다. 그것을 먼저 읽고, 없으면
화면에 보이는 표(스펙 표)와 목록(특징 목록)에서 찾습니다.
"""
from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup

from . import catalog

MAX_SPECS = 60
MAX_FEATURES = 12

_NEW_BADGE = re.compile(
    r"(^|[^a-z])(new|all-new|newly launched|neu|nouveau|nouvelle|nuevo|novo|nova)([^a-z]|$)|신제품|신모델",
    re.I,
)
_PRICE_NUMBER = re.compile(r"\d[\d.,\s ]*")


# ── 가격 글자 → 숫자 ────────────────────────────────────────────────────
def parse_price(value: Any, default_currency: str = "USD") -> tuple[float | None, str]:
    """'$1,299.99', '1.299,00 €', '₩1,390,000', 1299 → (숫자, 통화)."""
    if value is None or value == "":
        return None, default_currency
    if isinstance(value, (int, float)):
        return float(value), default_currency
    text = str(value).strip()
    currency = default_currency
    for symbol in sorted(catalog.SYMBOL_CURRENCY, key=len, reverse=True):
        if symbol in text:
            currency = catalog.SYMBOL_CURRENCY[symbol]
            break
    code = re.search(r"\b([A-Z]{3})\b", text)
    if code and code.group(1) in catalog.fx_rates():
        currency = code.group(1)
    match = _PRICE_NUMBER.search(text)
    if not match:
        return None, currency
    number = re.sub(r"[\s ]", "", match.group(0)).strip(".,")
    # 마지막 구분 기호 뒤가 2자리면 소수점, 아니면 천 단위 구분으로 봅니다.
    last = max(number.rfind(","), number.rfind("."))
    if last != -1 and len(number) - last - 1 == 2:
        whole = re.sub(r"[.,]", "", number[:last])
        number = f"{whole}.{number[last + 1:]}"
    else:
        number = re.sub(r"[.,]", "", number)
    try:
        return float(number), currency
    except ValueError:
        return None, currency


# ── JSON-LD ─────────────────────────────────────────────────────────────
def _walk(node: Any):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


def _is_product(node: dict) -> bool:
    kind = node.get("@type")
    kinds = kind if isinstance(kind, list) else [kind]
    return any(str(k).lower() in ("product", "productmodel", "individualproduct") for k in kinds)


def _json_ld_product(soup: BeautifulSoup) -> dict:
    for script in soup.find_all("script", type=re.compile("ld\\+json", re.I)):
        try:
            data = json.loads(script.string or script.get_text() or "")
        except (json.JSONDecodeError, TypeError):
            continue
        for node in _walk(data):
            if _is_product(node):
                return node
    return {}


def _first(value: Any) -> Any:
    return value[0] if isinstance(value, list) and value else value


def _text(value: Any) -> str:
    value = _first(value)
    if isinstance(value, dict):
        value = value.get("name") or value.get("url") or value.get("@id") or ""
    return re.sub(r"\s+", " ", str(value or "")).strip()


# ── 화면에 보이는 표와 목록 ────────────────────────────────────────────
def _spec_tables(soup: BeautifulSoup) -> dict[str, str]:
    specs: dict[str, str] = {}
    for row in soup.select("table tr"):
        cells = row.find_all(["th", "td"])
        if len(cells) == 2:
            key, val = (c.get_text(" ", strip=True) for c in cells)
            if key and val and len(key) < 80:
                specs.setdefault(key, val[:200])
    for dl in soup.find_all("dl"):
        for dt in dl.find_all("dt"):
            dd = dt.find_next_sibling("dd")
            if dd:
                key, val = dt.get_text(" ", strip=True), dd.get_text(" ", strip=True)
                if key and val and len(key) < 80:
                    specs.setdefault(key, val[:200])
    # class 이름에 spec 이 든 "이름: 값" 줄
    for node in soup.select("[class*=spec] li, [class*=Spec] li"):
        text = node.get_text(" ", strip=True)
        if ":" in text:
            key, val = (t.strip() for t in text.split(":", 1))
            if key and val and len(key) < 80:
                specs.setdefault(key, val[:200])
    return dict(list(specs.items())[:MAX_SPECS])


def _features(soup: BeautifulSoup) -> list[str]:
    """특징·장점 목록. POD(차별점) 후보가 됩니다."""
    found: list[str] = []
    selectors = [
        "[class*=feature] li", "[class*=Feature] li", "[class*=highlight] li",
        "[class*=benefit] li", "[class*=key] li", "[class*=usp] li",
        "[class*=feature] h3", "[class*=Feature] h3", "[class*=feature] h4",
    ]
    for selector in selectors:
        for node in soup.select(selector):
            text = node.get_text(" ", strip=True)
            if 8 <= len(text) <= 220 and text not in found:
                found.append(text)
    return found[:MAX_FEATURES]


def _meta(soup: BeautifulSoup, *names: str) -> str:
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return tag["content"].strip()
    return ""


def _itemprop(soup: BeautifulSoup, name: str) -> str:
    tag = soup.find(attrs={"itemprop": name})
    if not tag:
        return ""
    return (tag.get("content") or tag.get_text(" ", strip=True) or "").strip()


# ── 한 페이지 전체 ─────────────────────────────────────────────────────
def extract_product(html: str, url: str, default_currency: str = "USD") -> dict | None:
    """제품 페이지면 정리한 dict, 제품 페이지가 아니면 None."""
    soup = BeautifulSoup(html, "html.parser")
    ld = _json_ld_product(soup)

    name = _text(ld.get("name")) or _meta(soup, "og:title") or _text(soup.title.string if soup.title else "")
    model = _text(ld.get("model")) or _text(ld.get("mpn")) or _text(ld.get("sku")) or _itemprop(soup, "sku")

    offers = _first(ld.get("offers")) or {}
    if isinstance(offers, dict) and offers.get("@type", "").lower() == "aggregateoffer":
        raw_price = offers.get("lowPrice") or offers.get("price")
    else:
        raw_price = offers.get("price") if isinstance(offers, dict) else None
    currency = (offers.get("priceCurrency") if isinstance(offers, dict) else "") or ""
    if raw_price in (None, ""):
        raw_price = _meta(soup, "product:price:amount", "og:price:amount") or _itemprop(soup, "price")
        currency = currency or _meta(soup, "product:price:currency", "og:price:currency") or _itemprop(
            soup, "priceCurrency"
        )
    price, guessed = parse_price(raw_price, currency or default_currency)
    currency = (currency or guessed).upper()

    specs: dict[str, str] = {}
    for prop in ld.get("additionalProperty") or []:
        if isinstance(prop, dict) and prop.get("name"):
            specs[_text(prop["name"])] = _text(prop.get("value"))
    for key, val in _spec_tables(soup).items():
        specs.setdefault(key, val)

    description = _text(ld.get("description")) or _meta(soup, "og:description", "description")
    features = _features(soup)

    # 제품 카드도 없고 가격도 스펙도 없으면 제품 페이지가 아닌 것으로 봅니다.
    if not ld and price is None and len(specs) < 3:
        return None

    badge_text = " ".join(
        n.get_text(" ", strip=True) for n in soup.select("[class*=badge], [class*=flag], [class*=label]")
    )
    return {
        "url": url,
        "name": name[:200],
        "model": model[:80],
        "brand": _text(ld.get("brand")),
        "price": price,
        "currency": currency,
        "image": _text(ld.get("image")) or _meta(soup, "og:image"),
        "release_date": _text(ld.get("releaseDate"))[:10],
        "new_badge": bool(_NEW_BADGE.search(f"{badge_text} {name}")),
        "description": description[:600],
        "features": features,
        "specs": specs,
    }
