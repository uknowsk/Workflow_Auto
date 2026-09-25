"""가전 신제품 조사 앱 테스트.

진짜 제조사 사이트 대신 가짜 사이트 두 개를 만들어 인터넷 없이 돌립니다.
  - 가짜 GE: robots.txt → 사이트맵 목록 → 제품 사이트맵 (제품 카드 JSON-LD 있음)
  - 가짜 Whirlpool: 사이트맵 없음 → 첫 화면 메뉴 → 품목 목록 페이지 → 제품 (스펙 표만 있음)
"""
import json

import pytest
from starlette.testclient import TestClient

from appliance_watch import catalog, discover, extract, pod, service, web

GE = "https://www.geappliances.com"
WP = "https://www.whirlpool.com"


def _ge_product(model, name, price, release, features, specs):
    card = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": name,
        "model": model,
        "brand": {"@type": "Brand", "name": "GE"},
        "releaseDate": release,
        "offers": {"@type": "Offer", "price": price, "priceCurrency": "USD"},
        "additionalProperty": [{"@type": "PropertyValue", "name": k, "value": v} for k, v in specs.items()],
    }
    items = "".join(f"<li>{f}</li>" for f in features)
    return (
        f"<html><head><title>{name}</title>"
        f"<script type='application/ld+json'>{json.dumps(card)}</script></head>"
        f"<body><ul class='key-features'>{items}</ul></body></html>"
    )


def _wp_product(name, price, features, specs):
    rows = "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in specs.items())
    items = "".join(f"<li>{f}</li>" for f in features)
    return (
        f"<html><head><meta property='og:title' content='{name}'>"
        f"<meta property='product:price:amount' content='{price}'>"
        f"<meta property='product:price:currency' content='USD'></head>"
        f"<body><span class='badge'>New</span><div class='features'><ul>{items}</ul></div>"
        f"<table class='specs'>{rows}</table></body></html>"
    )


def _pages(extra=None):
    pages = {
        f"{GE}/robots.txt": f"User-agent: *\nDisallow: /checkout/\nSitemap: {GE}/sitemap_index.xml\n",
        f"{GE}/sitemap_index.xml": (
            "<sitemapindex xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"
            f"<sitemap><loc>{GE}/sitemap-blog.xml</loc></sitemap>"
            f"<sitemap><loc>{GE}/sitemap-products.xml</loc></sitemap>"
            "</sitemapindex>"
        ),
        f"{GE}/sitemap-blog.xml": "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'></urlset>",
        f"{GE}/sitemap-products.xml": (
            "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"
            f"<url><loc>{GE}/appliance/GE-Profile-Smart-Range-PGS960YPFS</loc><lastmod>2026-09-01</lastmod></url>"
            f"<url><loc>{GE}/appliance/GE-Gas-Range-JGB735SPSS</loc><lastmod>2025-02-01</lastmod></url>"
            f"<url><loc>{GE}/appliance/GE-Refrigerator-GNE27JYMFS</loc><lastmod>2026-08-01</lastmod></url>"
            f"<url><loc>{GE}/support/range-manuals</loc></url>"
            "</urlset>"
        ),
        f"{GE}/appliance/GE-Profile-Smart-Range-PGS960YPFS": _ge_product(
            "PGS960YPFS",
            "GE Profile 30in Smart Slide-In Range",
            "3299.00",
            "2026-08-20",
            ["Built-in air fry with no preheat", "Precision cooking probe with app guidance", "Edge-to-edge cooktop"],
            {"Capacity": "5.3 cu. ft.", "Fuel": "Gas", "Width": "30 in"},
        ),
        f"{GE}/appliance/GE-Gas-Range-JGB735SPSS": _ge_product(
            "JGB735SPSS",
            "GE 30in Free-Standing Gas Range",
            "1099.00",
            "2024-03-01",
            ["Edge-to-edge cooktop", "Self-clean oven with steam clean option"],
            {"Capacity": "5.0 cu. ft.", "Fuel": "Gas", "Width": "30 in"},
        ),
        # Whirlpool 은 robots.txt / 사이트맵이 없습니다 (가짜 사이트에 없는 주소는 404)
        f"{WP}": (
            "<html><body><nav><a href='/kitchen/cooking/ranges/'>Ranges</a>"
            "<a href='/laundry/'>Laundry</a></nav></body></html>"
        ),
        f"{WP}/kitchen/cooking/ranges/": (
            "<html><body>"
            "<a href='/kitchen/cooking/ranges/p.WFES5030RZ.html'>Whirlpool Electric Range</a>"
            "<a href='/kitchen/cooking/ranges/p.WEE745H0LZ.html'>Whirlpool Smart Range</a>"
            "<a href='/support/'>Help</a>"
            "</body></html>"
        ),
        f"{WP}/kitchen/cooking/ranges/p.WFES5030RZ.html": _wp_product(
            "Whirlpool 5.3 cu. ft. Electric Range",
            "749",
            ["Frozen Bake technology skips preheating", "Edge-to-edge cooktop"],
            {"Capacity": "5.3 cu. ft.", "Fuel": "Electric", "Width": "30 in"},
        ),
        f"{WP}/kitchen/cooking/ranges/p.WEE745H0LZ.html": _wp_product(
            "Whirlpool 6.4 cu. ft. Smart Range with Air Fry",
            "$1,649.00",
            ["Scan-to-Cook technology with Yummly app", "Air fry mode without extra basket"],
            {"Capacity": "6.4 cu. ft.", "Fuel": "Electric", "Width": "30 in"},
        ),
    }
    pages.update(extra or {})
    return pages


@pytest.fixture
def fake_web(monkeypatch):
    pages = _pages()

    def raw_get(url):
        key = url.rstrip("/") if url.rstrip("/") in pages else url
        if key not in pages:
            raise web.FetchError(f"404 {url}")
        return pages[key]

    monkeypatch.setattr(web, "_raw_get", raw_get)
    monkeypatch.setattr(web, "CRAWL_DELAY", 0)
    monkeypatch.setattr(pod, "LLM_BASE_URL", "")
    monkeypatch.setattr(discover, "SEARCH_PROVIDER", "")
    web.reset()
    # 테스트마다 저장소를 비웁니다
    for kind in ("product", "source", "scan", "watch", "region_makers"):
        for record in service.store.list(kind):
            service.store.delete(record["id"])
    service.set_region_makers(
        "north_america",
        [{"name": "GE Appliances", "site": GE}, {"name": "Whirlpool", "site": WP}],
    )
    yield pages
    web.reset()


# ── 작은 부품 ──────────────────────────────────────────────────────────
def test_가격_글자를_나라별_모양대로_읽는다():
    assert extract.parse_price("$1,299.99") == (1299.99, "USD")
    assert extract.parse_price("1.299,00 €") == (1299.0, "EUR")
    assert extract.parse_price("₩1,390,000") == (1390000.0, "KRW")
    assert extract.parse_price("R$ 4.599,90") == (4599.9, "BRL")
    assert extract.parse_price("", "AUD") == (None, "AUD")


def test_품목은_낱말_단위로_알아본다():
    assert catalog.category_of("/appliances/ranges/gas-range-x") == "cooking"
    assert catalog.category_of("/four-door-refrigerator") == "refrigerator"
    assert catalog.category_of("/orange-juicer") == ""
    assert catalog.category_of("/kr/전자레인지/abc") == "cooking"


def test_가격대는_달러로_바꿔_나눈다():
    assert catalog.band_of(catalog.to_usd(1380000, "KRW"), "cooking") == "중급형"
    assert catalog.band_of(5000, "cooking") == "최고급"
    assert catalog.band_of(None, "cooking") == "가격 미확인"


def test_제품처럼_생긴_주소만_고른다():
    assert discover.looks_like_product(f"{GE}/appliance/GE-Gas-Range-JGB735SPSS")
    assert discover.looks_like_product(f"{WP}/kitchen/cooking/ranges/p.WFES5030RZ.html")
    assert not discover.looks_like_product(f"{GE}/support/range-manuals")
    assert not discover.looks_like_product(f"{WP}/kitchen/cooking/ranges/")


def test_POD는_경쟁사에_없는_특징을_고른다():
    me = {"features": ["Edge-to-edge cooktop", "Built-in air fry with no preheat"]}
    peers = [{"features": ["Edge-to-edge cooktop", "Self-clean oven"]}]
    assert pod.heuristic_pods(me, peers, limit=1) == ["Built-in air fry with no preheat"]


# ── 출처 찾기 ─────────────────────────────────────────────────────────
def test_사이트맵에서_품목_제품만_최신순으로_찾는다(fake_web):
    disc = discover.discover("GE Appliances", "north_america", "cooking", GE)
    urls = [c.url for c in disc.candidates]
    assert urls[0].endswith("PGS960YPFS")  # 2026-09 로 가장 최근
    assert not any("Refrigerator" in u or "support" in u for u in urls)
    assert disc.sources[0]["type"] == "sitemap"


def test_사이트맵이_없으면_메뉴를_따라간다(fake_web):
    disc = discover.discover("Whirlpool", "north_america", "cooking", WP)
    assert len(disc.candidates) == 2
    assert disc.sources[0] == {"type": "listing", "url": f"{WP}/kitchen/cooking/ranges/", "hits": 2}


# ── 전체 흐름 ─────────────────────────────────────────────────────────
def test_조사하면_가격_POD_스펙이_정리된다(fake_web):
    result = service.scan("north_america", "cooking")
    assert result["ok"] and result["product_count"] == 4

    by_model = {p.get("model") or p["name"]: p for p in result["products"]}
    profile = by_model["PGS960YPFS"]
    assert profile["price_usd"] == 3299.0 and profile["band"] == "프리미엄"
    assert profile["specs"]["Capacity"] == "5.3 cu. ft."
    assert profile["is_new"] and profile["new_reason"] == "출시일 2026-08-20"
    assert "Edge-to-edge cooktop" not in profile["pods"]  # 모두 가진 특징은 차별점이 아님
    assert "Built-in air fry with no preheat" in profile["pods"]

    old = by_model["JGB735SPSS"]
    assert old["is_new"] is False and old["band"] == "중급형"

    whirlpool = [p for p in result["products"] if p["maker"] == "Whirlpool"]
    assert {p["band"] for p in whirlpool} == {"보급형", "중급형"}
    assert all(p["new_reason"] == "페이지에 NEW 표시" for p in whirlpool)

    # 찾은 출처는 저장돼 다음 번에 먼저 쓰입니다
    assert {s["type"] for s in service.list_sources("north_america", "cooking")} == {"sitemap", "listing"}


def test_두번째_조사에서_새로_보인_제품은_신제품이다(fake_web):
    service.scan("north_america", "cooking", ["GE Appliances"])
    new_url = f"{GE}/appliance/GE-Induction-Range-PHS93XYPFS"
    fake_web[f"{GE}/sitemap-products.xml"] = fake_web[f"{GE}/sitemap-products.xml"].replace(
        "</urlset>", f"<url><loc>{new_url}</loc><lastmod>2026-09-20</lastmod></url></urlset>"
    )
    fake_web[new_url] = _ge_product(
        "PHS93XYPFS", "GE Profile Induction Range", "3899", "", ["Induction cooktop with sync burners"], {"Fuel": "Induction"}
    )
    web.reset()

    result = service.scan("north_america", "cooking", ["GE Appliances"])
    newbie = [p for p in result["products"] if p["model"] == "PHS93XYPFS"][0]
    assert newbie["new_reason"] == "지난 조사 이후 새로 등장"
    assert newbie["band"] == "최고급"


def test_가격대별로_나눠_비교한다(fake_web):
    service.scan("north_america", "cooking")
    fixed = service.compare("north_america", "cooking")
    counts = {b["label"]: b["count"] for b in fixed["bands"]}
    assert counts == {"보급형": 1, "중급형": 2, "프리미엄": 1, "최고급": 0}
    assert "Capacity" in fixed["spec_keys"]

    quantile = service.compare("north_america", "cooking", mode="quantile")
    assert [b["count"] for b in quantile["bands"]] == [1, 1, 1, 1]
    assert quantile["bands"][0]["max_usd"] < quantile["bands"][-1]["min_usd"]

    only_ge = service.compare("north_america", "cooking", makers=["GE Appliances"])
    assert sum(b["count"] for b in only_ge["bands"]) == 2


def test_감시_목록은_때가_된_것만_돈다(fake_web):
    watch = service.add_watch("north_america", "cooking", ["Whirlpool"], every_hours=24)
    first = service.run_due_watches()
    assert len(first) == 1 and "제품 2개" in first[0]["summary"]
    assert service.run_due_watches() == []  # 24시간이 안 지났으므로
    assert service.store.get(watch["id"])["last_result"].startswith("제품 2개")


def test_모르는_대륙이나_품목은_목록을_알려준다(fake_web):
    assert "regions" in service.scan("mars", "cooking")
    assert "categories" in service.scan("north_america", "spaceship")


# ── 화면용 주소 ───────────────────────────────────────────────────────
def test_화면용_주소로_조사하고_비교한다(fake_web):
    from appliance_watch import server

    client = TestClient(server.build_app())
    catalog_view = client.get("/api/catalog").json()
    assert len(catalog_view["regions"]) == 5
    assert all(len(r["makers"]) >= 2 for r in catalog_view["regions"])

    scanned = client.post("/api/scan", json={"region": "north_america", "category": "cooking", "makers": ["Whirlpool"]})
    assert scanned.status_code == 200 and scanned.json()["product_count"] == 2

    compared = client.get("/api/compare", params={"region": "north_america", "category": "cooking"}).json()
    assert compared["total"] == 2

    added = client.post(
        "/api/sources",
        json={"maker": "Whirlpool", "region": "north_america", "category": "cooking", "url": f"{WP}/kitchen/cooking/ranges/"},
    )
    assert added.json()["ok"]
    assert client.post("/api/sources", json={"url": "ftp://x"}).status_code == 400
