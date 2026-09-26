"""제품 정보가 "어디에" 올라오는지 스스로 찾아내는 곳.

사람이 새 사이트를 조사할 때 하는 순서를 그대로 따라 합니다.

  1) 공식 홈페이지 주소를 안다  → 모르면 검색해서 찾는다 (검색 API 가 있을 때)
  2) 사이트맵(sitemap.xml)을 본다 → 사이트가 스스로 적어 둔 "전체 페이지 목록".
     여기서 품목 낱말(oven, range ...)이 든 주소만 고르고, 최근에 바뀐 순으로 줄 세운다.
  3) 사이트맵이 없거나 비었으면 첫 화면의 메뉴 링크를 따라 품목 목록 페이지로 가서
     제품처럼 생긴 링크를 모은다.
  4) 검색 API 가 있으면 "회사 + new + 품목" 으로 한 번 더 찾아 빈 곳을 채운다.

찾은 곳(출처)은 저장해 두고 다음 번에 먼저 씁니다. 잘 된 출처는 점수가 올라가고
실패한 출처는 내려가서, 돌릴수록 똑똑해집니다.
"""
from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from . import catalog, web

SEARCH_PROVIDER = os.getenv("SEARCH_PROVIDER", "").lower()  # searxng | brave | ""
SEARCH_API_URL = os.getenv("SEARCH_API_URL", "")
SEARCH_API_KEY = os.getenv("SEARCH_API_KEY", "")

MAX_SITEMAPS = int(os.getenv("DISCOVER_MAX_SITEMAPS", "12"))
# 카테고리 하나(예: cooking)에도 ranges/cooktops/wall-ovens/microwaves 처럼
# 하위 품목이 여러 개라, 4개로는 첫 하위 품목 하나만 보고 끝나버립니다.
MAX_LISTING_PAGES = int(os.getenv("DISCOVER_MAX_LISTING_PAGES", "12"))

# 주소가 이렇게 생겼으면 "제품 한 개의 상세 페이지"일 가능성이 높습니다.
#   /p/..., /p.모델.html(Whirlpool), /product/...,
#   모델명처럼 영문+숫자가 한 덩어리로 붙은 긴 토막(WRS325SDHZ, JGB735SPSS)
#   "ranges-2026" 처럼 낱말과 연도가 하이픈으로 떨어져 있는 것은 모델명이 아닙니다.
_PRODUCT_HINTS = re.compile(r"/(p|pd|product|products|produkt|produit|produto|model|sku)[/.]", re.I)
_MODEL_TOKEN = re.compile(r"(?<![a-z0-9])(?=[a-z0-9]*\d)(?=[a-z0-9]*[a-z])[a-z0-9]{6,}", re.I)
# "kitchen/.../p.html" 처럼 힌트 낱말 하나만 파일명 전체인 주소는 제품이 아니라
# 그 품목의 "시작 페이지"(카테고리 랜딩)인 경우가 많습니다(예: Whirlpool 의 p.html).
_BARE_HINT_STEM = {"p", "pd", "product", "products", "produkt", "produit", "produto", "model", "sku"}
_FILE_EXT = re.compile(r"\.(html?|php|aspx?|jsp)$", re.I)
# 이런 주소는 제품이 아닙니다.
_NOT_PRODUCT = re.compile(
    r"(support|manual|parts|accessor|review|compar|faq|blog|recipe|warranty|"
    r"register|search|login|cart|promotion|offers|\.pdf$|\.jpg$|\.png$)",
    re.I,
)
_VIA_PRIORITY = {"manual": 3, "listing": 2, "search": 2, "sitemap": 1}


@dataclass
class Candidate:
    url: str
    lastmod: str = ""
    via: str = ""  # sitemap | listing | search | manual


@dataclass
class Discovery:
    maker: str
    site: str
    candidates: list[Candidate] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)  # 어디서 찾았는지 (저장용)
    notes: list[str] = field(default_factory=list)  # 사람에게 보여 줄 진행 메모


def looks_like_product(url: str) -> bool:
    path = urlparse(url).path
    if _NOT_PRODUCT.search(path):
        return False
    last = ([seg for seg in path.split("/") if seg][-1:] or [""])[0]
    stem = _FILE_EXT.sub("", last).lower()
    if _PRODUCT_HINTS.search(path):
        # "p.html" 처럼 힌트 낱말 하나뿐이면 모델명이 있어야 진짜 제품 페이지로 칩니다.
        if stem in _BARE_HINT_STEM:
            return bool(_MODEL_TOKEN.search(stem))
        return True
    return bool(_MODEL_TOKEN.search(stem))


def _same_site(url: str, site: str) -> bool:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    base = urlparse(site).netloc.lower().removeprefix("www.")
    return host == base or host.endswith("." + base)


def _under_site_path(url: str, site: str) -> bool:
    """samsung.com/us 처럼 나라가 경로로 갈리는 사이트는 그 경로 아래만 봅니다."""
    prefix = urlparse(site).path.rstrip("/")
    return not prefix or urlparse(url).path.startswith(prefix + "/")


# ── 1) 공식 홈페이지 찾기 ────────────────────────────────────────────────
def search(query: str, limit: int = 10) -> list[str]:
    """설정된 검색 API 로 찾은 주소들. 검색 API 가 없으면 빈 목록."""
    if not SEARCH_PROVIDER or not SEARCH_API_URL:
        return []
    try:
        with httpx.Client(timeout=web.TIMEOUT) as client:
            if SEARCH_PROVIDER == "brave":
                response = client.get(
                    SEARCH_API_URL,
                    params={"q": query, "count": limit},
                    headers={"X-Subscription-Token": SEARCH_API_KEY, "Accept": "application/json"},
                )
                items = response.json().get("web", {}).get("results", [])
            else:  # searxng (사내에 직접 띄우기 쉬운 오픈소스 검색)
                response = client.get(
                    SEARCH_API_URL.rstrip("/") + "/search",
                    params={"q": query, "format": "json"},
                )
                items = response.json().get("results", [])
    except Exception:
        return []
    return [item.get("url", "") for item in items if item.get("url")][:limit]


def find_official_site(maker: str, region: str) -> str:
    """검색으로 그 대륙의 공식 홈페이지 주소를 짐작합니다."""
    label = catalog.REGIONS.get(region, {}).get("label", region)
    for url in search(f"{maker} official site home appliances {label}", limit=5):
        parts = urlparse(url)
        if parts.scheme.startswith("http") and not any(
            bad in parts.netloc for bad in ("wikipedia", "amazon", "youtube", "facebook", "linkedin")
        ):
            return f"{parts.scheme}://{parts.netloc}"
    return ""


# ── 2) 사이트맵 ─────────────────────────────────────────────────────────
def _parse_sitemap(text: str) -> tuple[list[str], list[Candidate]]:
    """사이트맵 하나를 읽어 (하위 사이트맵들, 페이지들)로 나눕니다."""
    try:
        root = ET.fromstring(text.encode("utf-8") if isinstance(text, str) else text)
    except ET.ParseError:
        return [], []
    children, pages = [], []
    for node in root.iter():
        tag = node.tag.rsplit("}", 1)[-1]
        if tag not in ("sitemap", "url"):
            continue
        loc = lastmod = ""
        for sub in node:
            sub_tag = sub.tag.rsplit("}", 1)[-1]
            if sub_tag == "loc":
                loc = (sub.text or "").strip()
            elif sub_tag == "lastmod":
                lastmod = (sub.text or "").strip()
        if not loc:
            continue
        if tag == "sitemap":
            children.append(loc)
        else:
            pages.append(Candidate(loc, lastmod[:10], "sitemap"))
    return children, pages


def _sitemap_priority(url: str, category: str) -> int:
    """하위 사이트맵이 많을 때 제품·품목 사이트맵을 먼저 열어 봅니다."""
    score = 0
    if re.search(r"product|pdp|catalog|model", url, re.I):
        score += 2
    if catalog.keyword_hit(url, category):
        score += 3
    if re.search(r"blog|news|support|image|video|recipe|store-locator", url, re.I):
        score -= 3
    return score


def from_sitemaps(site: str, category: str, disc: Discovery) -> None:
    parts = urlparse(site)
    origin = f"{parts.scheme}://{parts.netloc}"
    queue = web.robots_sitemaps(origin) or [f"{origin}/sitemap.xml", f"{origin}/sitemap_index.xml"]
    seen: set[str] = set()
    opened = 0
    while queue and opened < MAX_SITEMAPS:
        queue.sort(key=lambda u: -_sitemap_priority(u, category))
        sitemap_url = queue.pop(0)
        if sitemap_url in seen:
            continue
        seen.add(sitemap_url)
        try:
            text = web.fetch_text(sitemap_url)
        except Exception:
            continue
        opened += 1
        children, pages = _parse_sitemap(text)
        queue.extend(c for c in children if c not in seen)
        hits = [
            p
            for p in pages
            if _under_site_path(p.url, site)
            and catalog.keyword_hit(p.url, category)
            and looks_like_product(p.url)
        ]
        if hits:
            disc.candidates.extend(hits)
            disc.sources.append({"type": "sitemap", "url": sitemap_url, "hits": len(hits)})
    if opened == 0:
        disc.notes.append("사이트맵을 찾지 못했습니다.")


# ── 3) 메뉴 링크 따라가기 ────────────────────────────────────────────────
def _links(html: str, base: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for a in soup.find_all("a", href=True):
        href = urljoin(base, a["href"].split("#")[0])
        if href.startswith("http"):
            out.append((href, a.get_text(" ", strip=True)))
    return out


def _diversify_listings(urls: list[str], limit: int) -> list[str]:
    """같은 하위 품목(예: cooktops) 페이지만 잔뜩 고르지 않도록, 하위 품목마다 하나씩
    고루 뽑습니다. 'see-all' 처럼 전체 목록을 보여주는 주소가 있으면 그걸 우선 씁니다."""
    groups: dict[tuple[str, ...], str] = {}
    order: list[tuple[str, ...]] = []
    for url in urls:
        segments = tuple(seg for seg in urlparse(url).path.split("/") if seg)
        key = segments[:3]  # 예: kitchen/cooking/ranges
        if key not in groups:
            order.append(key)
            groups[key] = url
        elif "see-all" in url.lower() and "see-all" not in groups[key].lower():
            groups[key] = url
    return [groups[key] for key in order][:limit]


def from_listing_pages(site: str, category: str, disc: Discovery) -> None:
    try:
        home = web.fetch_text(site)
    except Exception as exc:
        disc.notes.append(f"첫 화면을 열지 못했습니다: {exc}")
        return
    # 첫 화면에서 품목 이름이 든 링크 = 품목 목록 페이지 후보
    raw_listings = []
    for href, text in _links(home, site):
        if not _same_site(href, site) or looks_like_product(href):
            continue
        if catalog.keyword_hit(f"{href} {text}", category) and href not in raw_listings:
            raw_listings.append(href)
    listings = _diversify_listings(raw_listings, MAX_LISTING_PAGES)
    for listing in listings:
        try:
            html = web.fetch_text(listing)
        except Exception:
            continue
        found = [
            Candidate(href, "", "listing")
            for href, _ in _links(html, listing)
            if _same_site(href, site) and looks_like_product(href)
        ]
        if found:
            disc.candidates.extend(found)
            disc.sources.append({"type": "listing", "url": listing, "hits": len(found)})


# ── 4) 검색 ────────────────────────────────────────────────────────────
def from_search(site: str, maker: str, category: str, disc: Discovery) -> None:
    label = catalog.CATEGORIES[category]["keywords"][0]
    host = urlparse(site).netloc
    query = f"site:{host} {maker} new {label}" if host else f"{maker} new {label}"
    found = [
        Candidate(url, "", "search")
        for url in search(query, limit=15)
        if (not host or _same_site(url, site)) and looks_like_product(url)
    ]
    if found:
        disc.candidates.extend(found)
        disc.sources.append({"type": "search", "url": query, "hits": len(found)})


# ── 전체 순서 ──────────────────────────────────────────────────────────
def discover(
    maker: str,
    region: str,
    category: str,
    site: str = "",
    known_sources: list[dict] | None = None,
) -> Discovery:
    """회사 하나 + 품목 하나에 대해 제품 상세 페이지 후보를 모읍니다."""
    if not site:
        site = find_official_site(maker, region)
    disc = Discovery(maker=maker, site=site)
    if not site:
        disc.notes.append("공식 홈페이지 주소를 모릅니다. 화면에서 직접 넣거나 검색 API 를 붙여 주세요.")
        return disc

    # 사람이 직접 넣었거나 예전에 잘 됐던 출처를 먼저 씁니다.
    for source in sorted(known_sources or [], key=lambda s: -s.get("score", 0)):
        if source.get("score", 0) < -2:
            continue
        if source.get("type") == "manual" and looks_like_product(source["url"]):
            disc.candidates.append(Candidate(source["url"], "", "manual"))
        elif source.get("type") in ("listing", "manual"):
            before = len(disc.candidates)
            try:
                html = web.fetch_text(source["url"])
                disc.candidates.extend(
                    Candidate(h, "", "listing")
                    for h, _ in _links(html, source["url"])
                    if _same_site(h, site) and looks_like_product(h)
                )
            except Exception:
                pass
            disc.sources.append(
                {"type": source["type"], "url": source["url"], "hits": len(disc.candidates) - before}
            )

    from_sitemaps(site, category, disc)
    # 사이트맵은 오래된 단종 제품이 많이 섞여 있을 수 있습니다(예: Whirlpool).
    # 지금 화면에 실제로 걸려 있는 품목 목록 페이지도 항상 같이 봐서 보완합니다.
    from_listing_pages(site, category, disc)
    if len(disc.candidates) < 3:
        from_search(site, maker, category, disc)

    # 같은 주소는 한 번만. 최근에 바뀐 것을 우선하고, 그 다음은 "지금 화면에
    # 실제로 걸려 있는 링크(listing/search)"를 사이트맵보다 앞에 둡니다 —
    # 사이트맵에는 이미 단종된 제품 주소가 오래 남아 있는 경우가 있어서입니다.
    unique: dict[str, Candidate] = {}
    for cand in disc.candidates:
        key = cand.url.rstrip("/")
        current = unique.get(key)
        if current is None:
            unique[key] = cand
            continue
        better_lastmod = cand.lastmod > current.lastmod
        same_lastmod = cand.lastmod == current.lastmod
        better_via = _VIA_PRIORITY.get(cand.via, 0) > _VIA_PRIORITY.get(current.via, 0)
        if better_lastmod or (same_lastmod and better_via):
            unique[key] = cand
    disc.candidates = sorted(
        unique.values(),
        key=lambda c: (c.lastmod, _VIA_PRIORITY.get(c.via, 0)),
        reverse=True,
    )
    if not disc.candidates:
        disc.notes.append("제품 페이지를 찾지 못했습니다. 품목 목록 페이지 주소를 직접 알려 주면 거기서부터 찾습니다.")
    return disc
