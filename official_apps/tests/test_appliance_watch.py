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
    for kind in ("product", "source", "scan", "watch", "region_makers", "custom_brand"):
        for record in service.store.list(kind):
            service.store.delete(record["id"])
    service.set_region_makers(
        "north_america",
        [{"name": "GE Appliances", "site": GE}, {"name": "Whirlpool", "site": WP}],
    )
    yield pages
    web.reset()


# ── 글로벌 탑 20 (대륙별 탑 5 대신) ───────────────────────────────────────
def test_글로벌_탑_20이_기본값이고_대륙_순위로_거르지_않는다():
    brands = catalog.global_brands()
    assert len(brands) == 20
    assert all("name" in b and "tier" in b for b in brands)
    names = {b["name"] for b in brands}
    # 북미 판매 순위엔 안 들어도 영향력 큰 프리미엄 브랜드가 빠지면 안 됩니다.
    assert {"Miele", "KitchenAid", "Bosch (BSH)"} <= names

    for region in catalog.REGIONS:
        makers = catalog.default_region_makers(region)
        assert len(makers) == 20  # 대륙마다 5개로 자르지 않고 20개 전부를 후보로 둡니다.
        assert {m["name"] for m in makers} == names


def test_모르는_홈페이지는_빈_문자열이지_에러가_아니다():
    assert catalog.brand_site("Viking", "asia") == ""
    assert catalog.brand_site("없는브랜드", "north_america") == ""


# ── 브랜드 이름+주소만으로 추가하기 ────────────────────────────────────────
# 주의: fake_web 픽스처가 north_america 는 GE·Whirlpool 2개짜리 목록으로 이미
# 바꿔 둡니다(set_region_makers). 그래서 "글로벌 탑 20 기본값" 개수를 보려면
# 손 안 댄 다른 대륙(europe 등)으로 확인합니다.
def test_이름과_주소만으로_새_브랜드를_추가한다(fake_web):
    service.add_brand("Sharp", "https://www.sharpusa.com")
    # region 을 안 정했으니 대륙과 상관없이(대륙별 회사 목록을 손 안 댄 곳도) 보여야 합니다.
    europe_makers = service.region_makers("europe")
    assert {"name": "Sharp", "site": "https://www.sharpusa.com"} in europe_makers
    assert len(europe_makers) == 21  # 글로벌 탑 20 + 새로 더한 1개
    assert any(m["name"] == "Sharp" for m in service.region_makers("north_america"))


def test_대륙을_정해서_추가하면_그_대륙에서만_보인다(fake_web):
    service.add_brand("Local Brand", "https://www.example.com", region="asia")
    assert any(m["name"] == "Local Brand" for m in service.region_makers("asia"))
    assert not any(m["name"] == "Local Brand" for m in service.region_makers("north_america"))


def test_같은_이름으로_다시_추가하면_주소만_바뀐다(fake_web):
    service.add_brand("Sharp", "https://old.example.com")
    service.add_brand("Sharp", "https://new.example.com")
    matches = [m for m in service.custom_brands() if m["name"] == "Sharp"]
    assert len(matches) == 1
    assert matches[0]["site"] == "https://new.example.com"


def test_이미_있는_글로벌_탑20_브랜드_주소도_고칠_수_있다(fake_web):
    service.add_brand("Viking", "https://www.new-viking-site.com")
    makers = service.region_makers("europe")  # 손 안 댄 대륙 = 글로벌 탑 20 기본값
    viking = next(m for m in makers if m["name"] == "Viking")
    assert viking["site"] == "https://www.new-viking-site.com"
    assert len(makers) == 20  # 새 브랜드가 아니라 기존 것을 고친 거라 개수는 그대로


def test_이름이나_주소가_없거나_http로_안_시작하면_거절한다(fake_web):
    with pytest.raises(ValueError):
        service.add_brand("", "https://example.com")
    with pytest.raises(ValueError):
        service.add_brand("Sharp", "www.example.com")  # http(s):// 없음
    with pytest.raises(ValueError):
        service.add_brand("Sharp", "https://example.com", region="화성")


def test_화면_API로_브랜드를_추가하고_카탈로그에서_확인한다(fake_web):
    from appliance_watch import server

    client = TestClient(server.build_app())
    added = client.post("/api/brands", json={"name": "Sharp", "url": "https://www.sharpusa.com"})
    assert added.status_code == 200 and added.json()["ok"]

    catalog_view = client.get("/api/catalog").json()
    assert any(b["name"] == "Sharp" and b["tier"] == "직접 추가" for b in catalog_view["global_brands"])
    na = next(r for r in catalog_view["regions"] if r["key"] == "north_america")
    assert any(m["name"] == "Sharp" for m in na["makers"])

    bad = client.post("/api/brands", json={"name": "Sharp", "url": "not-a-url"})
    assert bad.status_code == 400 and bad.json()["ok"] is False


# ── 작은 부품 ──────────────────────────────────────────────────────────
def test_가격_글자를_나라별_모양대로_읽는다():
    assert extract.parse_price("$1,299.99") == (1299.99, "USD")
    assert extract.parse_price("1.299,00 €") == (1299.0, "EUR")
    assert extract.parse_price("₩1,390,000") == (1390000.0, "KRW")
    assert extract.parse_price("R$ 4.599,90") == (4599.9, "BRL")
    assert extract.parse_price("", "AUD") == (None, "AUD")


def test_소수점_한_자리짜리_JSON_가격을_10배로_부풀리지_않는다():
    # JSON-LD offers.price 는 "1099.0" 처럼 소수점 뒤가 한 자리인 경우가 흔합니다.
    # 예전 규칙은 이걸 천 단위 구분으로 오해해서 10990.0 으로 읽었습니다.
    assert extract.parse_price("1099.0") == (1099.0, "USD")
    assert extract.parse_price("1199.2") == (1199.2, "USD")
    # 유럽식 천 단위 구분(점 뒤 세 자리)은 여전히 정수로 읽습니다.
    assert extract.parse_price("1.099", "EUR") == (1099.0, "EUR")


def test_GE처럼_이름과_모델이_og_title에_붙어있으면_나눠서_읽는다():
    # GE 는 JSON-LD 제품 카드가 없고, og:title 이 "이름|^|모델" 로 붙어 있습니다.
    # 모델명이 따로 없으면 주소 끝(URL 슬러그)에서도 찾아봅니다.
    html = (
        "<html><head>"
        "<meta property='og:title' content='GE® 30\" Free-Standing Electric Range|^|JBP27DMWW'>"
        "<meta property='product:price:amount' content='599'>"
        "<meta property='product:price:currency' content='USD'>"
        "</head><body><table><tr><th>Capacity</th><td>5.0 cu. ft.</td></tr>"
        "<tr><th>Fuel</th><td>Electric</td></tr><tr><th>Width</th><td>30 in</td></tr></table></body></html>"
    )
    url = "https://www.geappliances.com/appliance/GE-30-Free-Standing-Electric-Range-JBP27DMWW"
    product = extract.extract_product(html, url)
    assert product["name"] == 'GE® 30" Free-Standing Electric Range'
    assert product["model"] == "JBP27DMWW"
    assert product["price"] == 599.0


def test_두번_겹쳐_인코딩된_글자도_풀어서_읽는다():
    # Whirlpool 의 og:title 은 30&#34; 처럼 큰따옴표가 두 번 겹쳐 인코딩돼 있습니다
    # (원래 30" 인데 &#34; 로 한 번, 그 &amp;#34; 로 한 번 더).
    html_src = (
        "<html><head><meta property='og:title' content='30&amp;#34; Induction Cooktop|^|WCIT7530SB'>"
        "<meta property='product:price:amount' content='1099'>"
        "<meta property='product:price:currency' content='USD'></head>"
        "<body><table><tr><th>Capacity</th><td>1.8 cu. ft.</td></tr>"
        "<tr><th>Fuel</th><td>Electric</td></tr><tr><th>Width</th><td>30 in</td></tr></table></body></html>"
    )
    product = extract.extract_product(html_src, "https://www.whirlpool.com/x/p.a.wcit7530sb.html")
    assert product["name"] == '30" Induction Cooktop'


def test_에너지_효율은_스펙_표_항목_이름으로_찾는다():
    specs = {"Capacity": "5.3 cu. ft.", "Annual Energy Use": "220 kWh/yr", "Width": "30 in"}
    assert extract._energy_rating(specs, "", "") == "Annual Energy Use: 220 kWh/yr"


def test_에너지_효율은_배지_설명에서도_찾는다():
    # 스펙 표에 없어도 "Energy Star" 배지나 숫자+kWh 문구가 있으면 찾습니다.
    assert extract._energy_rating({}, "ENERGY STAR Certified", "") == "Energy Star Certified"
    assert extract._energy_rating({}, "", "Uses only 210 kWh/year of electricity.") == "210 kWh/year"
    assert extract._energy_rating({}, "", "Rated Energy Class A+++ for efficiency.") == "Energy Class A+++"
    # 아무 단서도 없으면 조용히 빈 문자열입니다(다른 스펙처럼 억지로 채우지 않음).
    assert extract._energy_rating({"Width": "30 in"}, "New!", "A great range.") == ""


def test_제품_카드의_고객_평점을_읽는다():
    ld = {"aggregateRating": {"@type": "AggregateRating", "ratingValue": "4.6", "reviewCount": "312"}}
    assert extract._page_rating(ld) == {"rating_value": 4.6, "rating_scale": 5.0, "rating_count": 312}
    # bestRating 이 따로 있으면(예: 10점 만점) 그대로 씁니다.
    ld10 = {"aggregateRating": {"ratingValue": "8.5", "bestRating": "10", "ratingCount": "9"}}
    assert extract._page_rating(ld10) == {"rating_value": 8.5, "rating_scale": 10.0, "rating_count": 9}
    # 평점이 없거나 깨져 있으면 조용히 빈 딕셔너리입니다.
    assert extract._page_rating({}) == {}
    assert extract._page_rating({"aggregateRating": {"ratingValue": "안 숫자"}}) == {}


def test_주소_끝_모델명으로도_찾는다():
    assert extract._model_from_url(
        "https://www.whirlpool.com/kitchen/cooking/cooktops/4-burner-elements/"
        "p.30-inch-gas-cooktop-with-ez-2-lift-hinged-cast-iron-grates.wcgk5030ps.html"
    ) == "WCGK5030PS"


def test_가격_0원은_가격_없음으로_본다():
    # 일부 제조사는 단종되거나 안 파는 제품을 가격 0으로 표시합니다.
    html = (
        "<html><head><meta property='og:title' content='Old Model|^|JVM1871SH'>"
        "<meta property='product:price:amount' content='0'>"
        "<meta property='product:price:currency' content='USD'></head>"
        "<body><table><tr><th>Capacity</th><td>1.8 cu. ft.</td></tr>"
        "<tr><th>Fuel</th><td>Electric</td></tr><tr><th>Width</th><td>30 in</td></tr></table></body></html>"
    )
    product = extract.extract_product(html, "https://www.geappliances.com/appliance/x-JVM1871SH")
    assert product["price"] is None


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


def test_특징_목록이_없으면_사이트_소개문구를_POD로_쓰지_않는다():
    # GE 처럼 특징 목록이 안 잡히고 og:description 이 사이트 공통 소개문구뿐인 경우,
    # "GE Appliances is your home for..." 같은 문장을 차별점으로 보여주면 안 됩니다.
    me = {
        "description": "GE Appliances is your home for the best kitchen appliances, home products, "
        "parts and accessories, and support."
    }
    assert pod.heuristic_pods(me, peers=[], limit=3) == []
    # 반대로 숫자·단위가 있어 이 제품 얘기임을 알 수 있으면 그대로 씁니다.
    specific = {"description": "5.3 cu. ft. capacity with Frozen Bake technology skips preheating."}
    assert pod.heuristic_pods(specific, peers=[], limit=3)


def test_AI_기능은_구체적인_표현이_있어야_잡는다():
    product = {
        "features": [
            "Scan-to-Cook technology with Yummly app",
            "Voice Control with a Compatible Voice-Enabled Device",
            "Edge-to-edge cooktop",  # AI/연결 기능 아님 — 안 잡혀야 함
        ]
    }
    assert pod.ai_features_from_rules(product) == [
        "Scan-to-Cook technology with Yummly app",
        "Voice Control with a Compatible Voice-Enabled Device",
    ]
    # "스마트"/"자동" 처럼 흔한 낱말 하나만으로는 안 잡습니다(오탐 방지).
    assert pod.ai_features_from_rules({"features": ["Smart design", "Automatic shut-off"]}) == []


def test_LLM_없으면_규칙으로_POD_AI기능_에너지효율을_채운다(monkeypatch):
    monkeypatch.setattr(pod, "LLM_BASE_URL", "")
    product = {
        "maker": "Whirlpool",
        "name": "Test Range",
        "band": "보급형",
        "energy_rating": "Energy Star Certified",  # 페이지에서 규칙으로 이미 찾은 값
        "features": [
            "Frozen Bake technology skips preheating",
            "Alexa built-in voice control",
        ],
    }
    result = pod.enrich_product(product, peers=[])
    assert result["pod_method"] == "rule"
    assert result["ai_method"] == "rule"
    assert result["ai_features"] == ["Alexa built-in voice control"]
    # 페이지에서 이미 찾은 에너지 효율 값은 LLM 없이도 그대로 남습니다.
    assert result["energy_rating"] == "Energy Star Certified"


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


def test_품목_목록_페이지_안의_다른_부서_제품은_안_섞인다(fake_web):
    # Samsung 처럼 한 페이지에 여러 부서 제품이 같이 링크된 큰 종합몰 사이트를
    # 흉내냅니다. 품목 목록 페이지 자체는 "cooking" 이 맞아도, 그 안의 TV
    # 링크(모델명처럼 생겨서 looks_like_product 는 통과함)까지 조리기기로
    # 잘못 집으면 안 됩니다.
    listing = f"{WP}/kitchen/cooking/ranges/"
    fake_web[listing] = fake_web[listing].replace(
        "</body>",
        "<a href='/tvs/qled/p.55-inch-qled-4k-tv.QN55Q60D.html'>55 inch QLED 4K TV</a></body>",
    )
    disc = discover.discover("Whirlpool", "north_america", "cooking", WP)
    urls = [c.url for c in disc.candidates]
    assert not any("QN55Q60D" in u for u in urls)
    assert len(disc.candidates) == 2  # 기존 레인지 2개만, TV 는 안 섞임


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
    # ai_features/energy_rating 필드가 저장까지 이어지는지(값이 없어도 키는 있어야 함).
    assert "ai_features" in profile and isinstance(profile["ai_features"], list)
    assert profile["ai_method"] in ("llm", "rule")

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


def test_단독_실행_화면이_바로_열린다(fake_web):
    # 이 앱 하나만 띄웠을 때(Workflow_Auto 없이) 바로 열어 보는 화면입니다.
    from appliance_watch import server

    client = TestClient(server.build_app())
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "가전 신제품 조사" in r.text
    assert "/api/catalog" in r.text  # 같은 앱의 API 를 부르는지


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


# ── 실제 사이트 주소 모양 (2026-09 검색으로 확인한 GE·Whirlpool 주소) ─────────
REAL_PRODUCTS = [
    "https://www.geappliances.com/appliance/GE-Profile-30-Smart-Slide-In-Front-Control-Gas-Double-Oven-Convection-Fingerprint-Resistant-Range-PGS960YPFS",
    "https://www.whirlpool.com/kitchen/cooking/ranges/electric/p.30-inch-electric-range-with-steam-clean.wfes3330rs.html",
    "https://www.whirlpool.com/kitchen/cooking/ranges/electric/p.WFES5030RB.html",
]
REAL_NOT_PRODUCTS = [
    "https://www.geappliances.com/appliances/ge-profile-ranges/",
    "https://www.geappliances.com/ge-appliances/kitchen/ranges/",
    "https://www.whirlpool.com/kitchen/cooking/ranges/electric.html",
    "https://www.whirlpool.com/kitchen/cooking/ranges/electric-comparison-chart.html",
    "https://www.whirlpool.com/kitchen/cooking/ranges-2026-lineup.html",
]


@pytest.mark.parametrize("url", REAL_PRODUCTS)
def test_실제_제품_주소는_조리기기_제품으로_본다(url):
    assert discover.looks_like_product(url) and catalog.keyword_hit(url, "cooking")


@pytest.mark.parametrize("url", REAL_NOT_PRODUCTS)
def test_목록_비교표_연도_페이지는_제품이_아니다(url):
    assert not discover.looks_like_product(url)


def test_같은_모델이_주소_두개로_올라와도_한번만_센다(fake_web):
    listing = f"{WP}/kitchen/cooking/ranges/"
    twin = f"{WP}/kitchen/cooking/ranges/p.30-inch-electric-range.wfes5030rz.html"
    fake_web[listing] = fake_web[listing].replace("</body>", f"<a href='{twin}'>same</a></body>")
    page = fake_web[f"{WP}/kitchen/cooking/ranges/p.WFES5030RZ.html"]
    fake_web[twin] = page.replace("<head>", "<head><meta itemprop='sku' content='WFES5030RZ'>")
    fake_web[f"{WP}/kitchen/cooking/ranges/p.WFES5030RZ.html"] = fake_web[twin]

    result = service.scan("north_america", "cooking", ["Whirlpool"])
    assert result["product_count"] == 2


# ── BM(벤치마크) 비교: 우위·동등·열세 ─────────────────────────────────────
def _seed_bm_product(url, **extra):
    base = {
        "url": url,
        "region": "north_america",
        "category": "cooking",
        "band": "500-1000",
        "maker": "GE",
        "name": "Range",
        "model": "X1",
        "price_usd": 800.0,
        "pods": [],
        "ai_features": [],
        "energy_rating": "",
    }
    base.update(extra)
    return service.store.put("product", base)


def test_평가한_점수가_없으면_먼저_찾아_저장해야_한다는_에러를_낸다(fake_web):
    with pytest.raises(ValueError):
        service.set_review_score("https://no-such.example/x", "Consumer Reports", 4.2)


def test_이름이나_점수가_이상하면_거절한다(fake_web):
    _seed_bm_product("https://a.example/1")
    with pytest.raises(ValueError):
        service.set_review_score("https://a.example/1", "  ", 4.0)
    with pytest.raises(ValueError):
        service.set_review_score("https://a.example/1", "Consumer Reports", "안숫자")


def test_점수를_넣으면_저장된_제품에_붙는다(fake_web):
    _seed_bm_product("https://a.example/1")
    updated = service.set_review_score("https://a.example/1", "Consumer Reports", 4.2, 5.0)
    assert updated["review_source"] == "Consumer Reports"
    assert updated["review_score"] == 4.2
    assert updated["review_scale"] == 5.0


def test_BM_대상도_먼저_찾아_저장해야_견줄_수_있다(fake_web):
    with pytest.raises(ValueError):
        service.benchmark("https://no-such.example/x")


def test_같은_가격대_제품끼리만_견준다(fake_web):
    _seed_bm_product("https://a.example/target", price_usd=800.0)
    _seed_bm_product("https://a.example/same-band", band="500-1000", price_usd=750.0)
    _seed_bm_product("https://a.example/other-band", band="1000-1500", price_usd=1200.0)
    _seed_bm_product("https://a.example/other-category", category="refrigerator", price_usd=800.0)

    result = service.benchmark("https://a.example/target")
    peer_urls = {row["url"] for row in result["rows"]}
    assert peer_urls == {"https://a.example/same-band"}


def test_가격이_싸고_POD가_많으면_그_축은_우위다(fake_web):
    _seed_bm_product("https://a.example/target", price_usd=800.0, pods=["a", "b", "c"])
    _seed_bm_product("https://a.example/peer", price_usd=1000.0, pods=["a"])

    result = service.benchmark("https://a.example/target")
    axes = result["rows"][0]["axes"]
    assert axes["price_usd"]["verdict"] == "우위"  # 더 쌈
    assert axes["pod_count"]["verdict"] == "우위"  # POD 더 많음
    assert "가격" in result["strengths"]
    assert "POD(차별점) 개수" in result["strengths"]


def test_차이가_8퍼센트_이내면_동등으로_본다(fake_web):
    _seed_bm_product("https://a.example/target", price_usd=1000.0)
    _seed_bm_product("https://a.example/peer", price_usd=1050.0)  # 5% 차이

    result = service.benchmark("https://a.example/target")
    assert result["rows"][0]["axes"]["price_usd"]["verdict"] == "동등"


def test_사람이_넣은_평가_점수가_페이지_평점보다_우선한다(fake_web):
    _seed_bm_product("https://a.example/target", rating_value=9.0, rating_scale=10.0)
    service.set_review_score("https://a.example/target", "Consumer Reports", 4.9, 5.0)
    _seed_bm_product("https://a.example/peer", rating_value=4.0, rating_scale=5.0)

    result = service.benchmark("https://a.example/target")
    # review_score(4.9/5) 를 썼다면 4.0/5보다 우위, rating_value(9/10=4.5/5) 를 썼어도 우위지만
    # 값 자체가 4.9로 반영됐는지 확인합니다.
    assert result["target"]["price_usd"] == 800.0
    axes = result["rows"][0]["axes"]
    assert axes["rating"]["target"] == pytest.approx(4.9)
    assert axes["rating"]["verdict"] == "우위"


def test_평점이_아예_없으면_그_축은_비교불가다(fake_web):
    _seed_bm_product("https://a.example/target")
    _seed_bm_product("https://a.example/peer")

    result = service.benchmark("https://a.example/target")
    assert result["rows"][0]["axes"]["rating"]["verdict"] == "비교불가"


def test_강점과_약점이_섞여도_따로_집계된다(fake_web):
    _seed_bm_product("https://a.example/target", price_usd=1200.0, pods=["a", "b"])
    _seed_bm_product("https://a.example/cheaper", price_usd=800.0, pods=[])
    _seed_bm_product("https://a.example/pricier", price_usd=2000.0, pods=[])

    result = service.benchmark("https://a.example/target")
    # 대상보다 싼 경쟁자 하나(가격 열세), 비싼 경쟁자 하나(가격 우위) → 팽팽하니 가격은 강점도 약점도 아님
    assert "가격" not in result["strengths"]
    assert "가격" not in result["weaknesses"]
    # POD는 둘 다한테 우위 → 강점
    assert "POD(차별점) 개수" in result["strengths"]


# ── 스파이더맵(레이더 차트) 정규화 ──────────────────────────────────────
def test_레이더는_가격대_안에서_0과_1사이로_맞춘다(fake_web):
    _seed_bm_product("https://a.example/target", price_usd=800.0, pods=["a", "b"])  # 가장 싸고 POD 가장 많음
    _seed_bm_product("https://a.example/mid", price_usd=1000.0, pods=["a"])
    _seed_bm_product("https://a.example/priciest", price_usd=1200.0, pods=[])  # 가장 비싸고 POD 없음

    result = service.benchmark("https://a.example/target")
    # 가격은 "낮을수록 유리"라 가장 싼 대상이 1(바깥쪽), 가장 비싼 경쟁자가 0(안쪽)
    assert result["target"]["radar"]["price_usd"] == 1.0
    priciest = next(r for r in result["rows"] if r["url"] == "https://a.example/priciest")
    assert priciest["radar"]["price_usd"] == 0.0
    # POD는 "많을수록 유리"라 대상이 가장 많으니 1
    assert result["target"]["radar"]["pod_count"] == 1.0
    assert priciest["radar"]["pod_count"] == 0.0


def test_레이더_값이_모두_같으면_가운데_0点5로_본다(fake_web):
    _seed_bm_product("https://a.example/target", price_usd=1000.0)
    _seed_bm_product("https://a.example/peer", price_usd=1000.0)

    result = service.benchmark("https://a.example/target")
    assert result["target"]["radar"]["price_usd"] == 0.5
    assert result["rows"][0]["radar"]["price_usd"] == 0.5


def test_레이더는_값이_없는_축은_None으로_비워둔다(fake_web):
    _seed_bm_product("https://a.example/target")  # rating 없음
    _seed_bm_product("https://a.example/peer")

    result = service.benchmark("https://a.example/target")
    assert result["target"]["radar"]["rating"] is None
    assert result["rows"][0]["radar"]["rating"] is None


# ── 시장점유율(제품 수 기준 비중) ────────────────────────────────────────
def test_점유율은_판매량이_아니라_이_가격대_제품_수_기준이다(fake_web):
    _seed_bm_product("https://a.example/target", maker="GE")
    _seed_bm_product("https://a.example/ge2", maker="GE")
    _seed_bm_product("https://a.example/wp1", maker="Whirlpool")
    _seed_bm_product("https://a.example/other-band", maker="Samsung", band="1000-1500")  # 다른 가격대는 빼야 함

    result = service.benchmark("https://a.example/target")
    shares = {row["maker"]: row for row in result["market_share"]}
    assert set(shares) == {"GE", "Whirlpool"}
    assert shares["GE"]["count"] == 2
    assert shares["GE"]["share_pct"] == pytest.approx(66.7, abs=0.1)
    assert shares["Whirlpool"]["count"] == 1
    assert shares["GE"]["is_target"] is True
    assert shares["Whirlpool"]["is_target"] is False
    assert result["market_share_note"]  # 판매량이 아니라는 설명이 항상 같이 온다


