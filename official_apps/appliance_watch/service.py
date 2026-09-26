"""조사 한 번의 전체 흐름과 저장·비교·주기 실행.

    제조사 목록 → (출처 찾기 → 제품 페이지 읽기) × 제조사 → POD 뽑기 → 저장
    저장된 제품 → 가격대로 나눠 비교

MCP 기능(server.py)과 화면용 주소(server.py 의 /api/*)가 둘 다 이 파일을 부릅니다.
"""
from __future__ import annotations

import os
import statistics
import threading
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from common.store import Store, now_iso

from . import catalog, discover, extract, pod, web

NEW_WITHIN_DAYS = int(os.getenv("NEW_WITHIN_DAYS", "180"))
MAX_PER_MAKER = int(os.getenv("SCAN_MAX_PER_MAKER", "8"))

store = Store("appliance_watch")
_scan_lock = threading.Lock()


# ── 사람이 이름+주소만으로 더한 브랜드 ────────────────────────────────────
def custom_brands() -> list[dict]:
    """브랜드 이름과 공식 홈페이지 주소만으로 추가한 브랜드들.

    region 이 비어 있으면 모든 대륙에서 이 주소를 씁니다.
    """
    return store.list("custom_brand")


def add_brand(name: str, site: str, region: str = "") -> dict:
    """브랜드 하나를 조사 대상에 추가합니다. 이름과 공식 홈페이지 주소만 있으면 됩니다.

    이미 있는 이름(글로벌 탑 20 포함)이면 그 주소를 바꾸는 걸로 봅니다 —
    코드(catalog.py)를 안 고치고도 잘못된 기본 주소를 바로잡을 수 있습니다.
    """
    name = str(name).strip()
    site = str(site).strip().rstrip("/")
    if not name:
        raise ValueError("브랜드 이름을 입력하세요.")
    if not site.startswith(("http://", "https://")):
        raise ValueError("공식 홈페이지 주소는 http:// 또는 https:// 로 시작해야 합니다.")
    if region and region not in catalog.REGIONS:
        raise ValueError(f"모르는 대륙입니다: {region}")
    # 같은 이름 + 같은 대륙(또는 둘 다 "모든 대륙")이면 주소만 갱신합니다.
    for old in store.list("custom_brand", name=name):
        if old.get("region", "") == region:
            store.delete(old["id"])
    return store.put("custom_brand", {"name": name, "site": site, "region": region})


def remove_brand(brand_id: str) -> bool:
    return store.delete(brand_id)


# ── 이 대륙에서 살펴볼 회사(기본값: 글로벌 탑 20 + 사람이 더한 브랜드) ─────
def region_makers(region: str) -> list[dict]:
    saved = store.list("region_makers", region=region)
    base = saved[-1]["makers"] if saved else catalog.default_region_makers(region)
    by_name: dict[str, dict] = {m["name"]: dict(m) for m in base}
    order = list(by_name.keys())
    for brand in custom_brands():
        if brand.get("region") and brand["region"] != region:
            continue  # 특정 대륙 전용으로 추가한 건데 지금 보는 대륙이 아닙니다.
        if brand["name"] not in by_name:
            order.append(brand["name"])
        by_name[brand["name"]] = {"name": brand["name"], "site": brand["site"]}
    return [by_name[name] for name in order]


def set_region_makers(region: str, makers: list[dict]) -> list[dict]:
    if region not in catalog.REGIONS:
        raise ValueError(f"모르는 대륙입니다: {region}")
    cleaned = [
        {"name": str(m.get("name", "")).strip(), "site": str(m.get("site", "")).strip().rstrip("/")}
        for m in makers
        if str(m.get("name", "")).strip()
    ]
    for old in store.list("region_makers", region=region):
        store.delete(old["id"])
    store.put("region_makers", {"region": region, "makers": cleaned})
    return cleaned


def catalog_view() -> dict:
    known_names = {b["name"] for b in catalog.GLOBAL_BRANDS}
    added_names = sorted({b["name"] for b in custom_brands() if b["name"] not in known_names})
    brands = catalog.global_brands() + [{"name": n, "tier": "직접 추가"} for n in added_names]
    return {
        "global_brands": brands,  # 영향력 기준 탑 20 + 사람이 이름/주소만으로 더한 브랜드
        "regions": [
            {"key": key, **info, "makers": region_makers(key)} for key, info in catalog.REGIONS.items()
        ],
        "categories": [
            {"key": key, "label": info["label"], "bands": catalog.band_ranges(key)}
            for key, info in catalog.CATEGORIES.items()
        ],
        "search_enabled": bool(discover.SEARCH_PROVIDER and discover.SEARCH_API_URL),
        "llm_enabled": bool(pod.POD_USE_LLM and pod.LLM_BASE_URL),
    }


# ── 출처 ───────────────────────────────────────────────────────────────
def list_sources(region: str = "", category: str = "", maker: str = "") -> list[dict]:
    return store.list("source", region=region, category=category, maker=maker)


def add_source(maker: str, region: str, category: str, url: str) -> dict:
    """사람이 직접 알려 준 출처(품목 목록 페이지나 제품 페이지)."""
    return _save_source(maker, region, category, {"type": "manual", "url": url.strip(), "hits": 0}, bump=3)


def _save_source(maker: str, region: str, category: str, source: dict, bump: int | None = None) -> dict:
    found = [s for s in list_sources(region, category, maker) if s["url"] == source["url"]]
    delta = bump if bump is not None else (1 if source.get("hits", 0) > 0 else -1)
    if found:
        current = found[0]
        return store.update(
            current["id"],
            score=current.get("score", 0) + delta,
            hits=source.get("hits", 0),
            last_checked=now_iso(),
        )
    return store.put(
        "source",
        {
            "maker": maker,
            "region": region,
            "category": category,
            "type": source["type"],
            "url": source["url"],
            "hits": source.get("hits", 0),
            "score": delta,
            "last_checked": now_iso(),
        },
    )


# ── 제품 ───────────────────────────────────────────────────────────────
def _days_ago(iso: str) -> int | None:
    try:
        day = date.fromisoformat(iso[:10])
    except (ValueError, TypeError):
        return None
    return (datetime.now(timezone.utc).date() - day).days


APPEARED = "지난 조사 이후 새로 등장"


def _new_reason(product: dict, had_baseline: bool, existing: dict | None) -> str:
    """신제품으로 볼 근거. 근거가 없으면 빈 문자열."""
    age = _days_ago(product.get("release_date", ""))
    if age is not None and 0 <= age <= NEW_WITHIN_DAYS:
        return f"출시일 {product['release_date']}"
    if product.get("new_badge"):
        return "페이지에 NEW 표시"
    if existing is None:
        return APPEARED if had_baseline else ""
    # 예전에 "새로 등장"으로 잡힌 제품은 처음 본 날부터 NEW_WITHIN_DAYS 동안 신제품으로 둡니다.
    seen_age = _days_ago(existing.get("first_seen", ""))
    if existing.get("new_reason") == APPEARED and seen_age is not None and seen_age <= NEW_WITHIN_DAYS:
        return APPEARED
    return ""


def list_products(
    region: str = "",
    category: str = "",
    maker: str = "",
    band: str = "",
    only_new: bool = False,
) -> list[dict]:
    items = store.list("product", region=region, category=category, maker=maker, band=band)
    if only_new:
        items = [p for p in items if p.get("is_new")]
    return sorted(items, key=lambda p: (p.get("price_usd") is None, p.get("price_usd") or 0))


def _upsert_product(data: dict) -> tuple[dict, bool]:
    existing = store.list("product", url=data["url"])
    if existing:
        current = existing[0]
        data = {**data, "first_seen": current.get("first_seen", current["created_at"][:10])}
        return store.update(current["id"], **data), True
    return store.put("product", {**data, "first_seen": now_iso()[:10]}), False


def set_review_score(url: str, source: str, score: float, scale: float = 5.0) -> dict:
    """Consumer Reports 같은 제3자 평가 점수를 사람이 직접 붙입니다.

    그런 곳은 구독이 있어야 점수가 보이는 경우가 많아서, 이 앱이 대신
    긁어오지 않습니다(가져올 수 있어도 재배포 약관 문제가 남습니다). 갖고
    계신 점수를 여기로 넣어 주시면 benchmark() 비교에서 페이지 자체 평점보다
    우선해서 씁니다.
    """
    products = store.list("product", url=url)
    if not products:
        raise ValueError("먼저 «신제품 찾기»로 이 제품을 찾아 저장해야 점수를 붙일 수 있습니다.")
    source = str(source).strip()
    if not source:
        raise ValueError("평가한 곳 이름(예: Consumer Reports)을 입력하세요.")
    try:
        score = float(score)
        scale = float(scale) or 5.0
    except (TypeError, ValueError):
        raise ValueError("점수는 숫자로 입력하세요.")
    return store.update(products[0]["id"], review_source=source, review_score=score, review_scale=scale)


def _scan_maker(maker: dict, region: str, category: str, limit: int, log: list[str]) -> list[dict]:
    currency = catalog.REGIONS[region]["currency"]
    known = list_sources(region, category, maker["name"])
    disc = discover.discover(maker["name"], region, category, maker.get("site", ""), known)
    if disc.site and not maker.get("site"):
        maker["site"] = disc.site  # 검색으로 찾은 홈페이지는 기억해 둡니다
    for source in disc.sources:
        _save_source(maker["name"], region, category, source)
    log.extend(f"[{maker['name']}] {note}" for note in disc.notes)
    log.append(f"[{maker['name']}] 후보 페이지 {len(disc.candidates)}곳")

    products = []
    seen_models: set[str] = set()
    # 사이트맵에는 이미 단종된 제품 주소가 오래 남아 있기도 해서(읽어도 진짜
    # 제품 정보가 안 나옴), 목표 개수의 3배보다 넉넉하게 시도합니다.
    window = max(limit * 3, min(len(disc.candidates), 40))
    dead_ends = 0
    for cand in disc.candidates[:window]:
        if len(products) >= limit:
            break
        try:
            html = web.fetch_text(cand.url)
        except Exception as exc:
            log.append(f"[{maker['name']}] 열지 못함: {exc}")
            dead_ends += 1
            continue
        product = extract.extract_product(html, cand.url, currency)
        if not product:
            dead_ends += 1
            continue
        # 같은 제품이 주소 두 개로 올라오는 사이트가 있습니다(Whirlpool: p.모델.html 과 긴 이름 주소).
        # 모델명이 같으면 한 번만 셉니다.
        model_key = (product.get("model") or "").upper()
        if model_key and model_key in seen_models:
            continue
        seen_models.add(model_key)
        price_usd = catalog.to_usd(product["price"], product["currency"])
        product.update(
            {
                "maker": maker["name"],
                "region": region,
                "category": category,
                "price_usd": price_usd,
                "band": catalog.band_of(price_usd, category),
                "page_updated": cand.lastmod,
                "found_via": cand.via,
                "last_seen": now_iso()[:10],
            }
        )
        products.append(product)
    log.append(f"[{maker['name']}] 제품 {len(products)}개 정리 (막힌 주소 {dead_ends}곳)")
    return products


def scan(region: str, category: str, makers: list[str] | None = None, max_per_maker: int = 0) -> dict:
    """대륙·품목을 골라 신제품을 찾고 정리해 저장합니다."""
    if region not in catalog.REGIONS:
        return {"ok": False, "error": f"모르는 대륙입니다: {region}", "regions": list(catalog.REGIONS)}
    if category not in catalog.CATEGORIES:
        return {"ok": False, "error": f"모르는 품목입니다: {category}", "categories": list(catalog.CATEGORIES)}
    if not _scan_lock.acquire(blocking=False):
        return {"ok": False, "error": "다른 조사가 돌고 있습니다. 끝난 뒤 다시 눌러 주세요."}
    try:
        limit = max_per_maker or MAX_PER_MAKER
        all_makers = region_makers(region)
        chosen = [m for m in all_makers if not makers or m["name"] in makers]
        log: list[str] = []
        found: list[dict] = []
        for maker in chosen:
            found.extend(_scan_maker(maker, region, category, limit, log))
        set_region_makers(region, all_makers)  # 검색으로 알아낸 홈페이지 주소 반영

        # POD·AI 기능·에너지 효율은 같은 품목의 다른 회사 제품들과 견줘서 정리합니다.
        others = list_products(region, category)
        saved, new_count = [], 0
        for product in found:
            peers = [
                p
                for p in [*found, *others]
                if p["url"] != product["url"] and p.get("maker") != product["maker"]
            ]
            same_band = [p for p in peers if p.get("band") == product["band"]]
            product.update(pod.enrich_product(product, same_band or peers))

            had_baseline = any(p.get("maker") == product["maker"] for p in others)
            existing = store.list("product", url=product["url"])
            reason = _new_reason(product, had_baseline, existing[0] if existing else None)
            product["is_new"] = bool(reason)
            product["new_reason"] = reason
            record, _ = _upsert_product(product)
            new_count += bool(reason)
            saved.append(record)

        store.put(
            "scan",
            {
                "region": region,
                "category": category,
                "makers": [m["name"] for m in chosen],
                "product_count": len(saved),
                "new_count": new_count,
                "log": log[-60:],
            },
        )
        return {
            "ok": True,
            "region": region,
            "category": category,
            "product_count": len(saved),
            "new_count": new_count,
            "products": saved,
            "log": log,
        }
    finally:
        _scan_lock.release()


def recent_scans(limit: int = 10) -> list[dict]:
    return list(reversed(store.list("scan")))[:limit]


# ── 가격대 비교 ────────────────────────────────────────────────────────
def _quantile_bands(items: list[dict]) -> list[dict]:
    """가격을 싼 것부터 줄 세워 4등분합니다. 이 묶음 안에서의 상대 위치로 보고 싶을 때."""
    priced = [p for p in items if p.get("price_usd") is not None]
    if not priced:
        return []
    priced.sort(key=lambda p: p["price_usd"])
    size = len(priced)
    bands = []
    for index, label in enumerate(catalog.BAND_LABELS):
        chunk = priced[index * size // 4 : (index + 1) * size // 4]
        if chunk:
            bands.append(
                {"label": label, "min_usd": chunk[0]["price_usd"], "max_usd": chunk[-1]["price_usd"], "products": chunk}
            )
    return bands


def compare(
    region: str = "",
    category: str = "cooking",
    makers: list[str] | None = None,
    mode: str = "fixed",
    only_new: bool = False,
) -> dict:
    """저장된 제품을 가격대별로 나눠 나란히 보여 줍니다.

    mode: fixed    = 품목별로 정해 둔 달러 경계 (대륙끼리 비교할 때)
          quantile = 지금 고른 제품들을 싼 순서로 4등분 (한 시장 안의 상대 위치)
    """
    items = list_products(region, category, only_new=only_new)
    if makers:
        items = [p for p in items if p.get("maker") in makers]

    if mode == "quantile":
        bands = _quantile_bands(items)
    else:
        bands = []
        for info in catalog.band_ranges(category):
            chunk = [p for p in items if p.get("band") == info["label"]]
            bands.append({**info, "products": chunk})

    for band in bands:
        prices = [p["price_usd"] for p in band["products"] if p.get("price_usd") is not None]
        band["count"] = len(band["products"])
        band["median_usd"] = round(statistics.median(prices), 2) if prices else None
        band["makers"] = dict(Counter(p.get("maker", "") for p in band["products"]))

    unpriced = [p for p in items if p.get("price_usd") is None]
    # 비교표 가로줄: 여러 제품에 공통으로 나오는 스펙 이름부터
    key_counts = Counter(k for p in items for k in (p.get("specs") or {}))
    spec_keys = [k for k, n in key_counts.most_common(15) if n >= 2] or [k for k, _ in key_counts.most_common(10)]
    return {
        "ok": True,
        "region": region,
        "category": category,
        "mode": mode,
        "total": len(items),
        "bands": bands,
        "unpriced": unpriced,
        "spec_keys": spec_keys,
    }


# ── BM(벤치마크) 비교: 우위·동등·열세 ─────────────────────────────────────
# 축마다 "낮을수록 유리"만 따로 표시하고, 나머지는 "높을수록 유리"로 봅니다.
_BM_AXES = ["price_usd", "pod_count", "rating", "energy", "ai_count"]
_BM_LABEL = {
    "price_usd": "가격",
    "pod_count": "POD(차별점) 개수",
    "rating": "평가 점수(5점 만점 환산)",
    "energy": "에너지 인증",
    "ai_count": "AI·연결 기능 개수",
}
_BM_LOWER_IS_BETTER = {"price_usd"}
_BM_TOLERANCE = 0.08  # 이 비율 안의 차이는 "동등" 으로 봅니다(오차·측정 방식 차이 감안)


def _bm_axis_value(product: dict, axis: str) -> float | None:
    if axis == "price_usd":
        return product.get("price_usd")
    if axis == "pod_count":
        return float(len(product.get("pods") or []))
    if axis == "rating":
        # 사람이 직접 넣은 제3자 점수(예: Consumer Reports)가 있으면 그걸 우선하고,
        # 없으면 제품 페이지 자체의 고객 평점을 5점 만점으로 환산해 씁니다.
        if product.get("review_score") is not None:
            scale = product.get("review_scale") or 5.0
            return product["review_score"] / scale * 5
        if product.get("rating_value") is not None:
            scale = product.get("rating_scale") or 5.0
            return product["rating_value"] / scale * 5
        return None
    if axis == "energy":
        return 1.0 if product.get("energy_rating") else 0.0
    if axis == "ai_count":
        return float(len(product.get("ai_features") or []))
    return None


def _bm_verdict(target_value: float | None, peer_value: float | None, axis: str) -> str:
    """target 이 peer 보다 우위/동등/열세인지. 둘 중 하나라도 없으면 "비교불가"."""
    if target_value is None or peer_value is None:
        return "비교불가"
    if target_value == peer_value == 0:
        return "동등"
    base = abs(peer_value) if peer_value else abs(target_value) or 1
    diff = (target_value - peer_value) / base
    if axis in _BM_LOWER_IS_BETTER:
        diff = -diff
    if abs(diff) <= _BM_TOLERANCE:
        return "동등"
    return "우위" if diff > 0 else "열세"


def benchmark(url: str) -> dict:
    """이 제품(BM 대상)을 같은 가격대의 다른 제품들과 견줍니다.

    가격·POD 개수·평가 점수·에너지 인증·AI 기능 개수, 다섯 축마다 경쟁 제품
    하나하나와 우위/동등/열세를 매기고, 우위가 많은 축을 강점(strengths)으로,
    열세가 많은 축을 약점(weaknesses)으로 정리합니다(SWOT 중 내부 요인 두 축 —
    기회·위협은 시장 전망 같은 이 앱 바깥의 판단이 필요해 다루지 않습니다).
    """
    targets = store.list("product", url=url)
    if not targets:
        raise ValueError("먼저 «신제품 찾기»로 이 제품을 찾아 저장해야 견줄 수 있습니다.")
    target = targets[0]
    peers = [
        p
        for p in store.list(
            "product", region=target["region"], category=target["category"], band=target["band"]
        )
        if p["url"] != url
    ]

    rows = []
    tally = {axis: Counter() for axis in _BM_AXES}
    for peer in peers:
        axes = {}
        for axis in _BM_AXES:
            tv, pv = _bm_axis_value(target, axis), _bm_axis_value(peer, axis)
            verdict = _bm_verdict(tv, pv, axis)
            axes[axis] = {"label": _BM_LABEL[axis], "target": tv, "peer": pv, "verdict": verdict}
            tally[axis][verdict] += 1
        rows.append(
            {
                "maker": peer.get("maker"),
                "name": peer.get("name"),
                "model": peer.get("model"),
                "price_usd": peer.get("price_usd"),
                "url": peer["url"],
                "axes": axes,
            }
        )

    strengths = [_BM_LABEL[a] for a in _BM_AXES if tally[a]["우위"] > tally[a]["열세"] and tally[a]["우위"] > 0]
    weaknesses = [_BM_LABEL[a] for a in _BM_AXES if tally[a]["열세"] > tally[a]["우위"] and tally[a]["열세"] > 0]

    return {
        "ok": True,
        "target": {
            "maker": target.get("maker"),
            "name": target.get("name"),
            "model": target.get("model"),
            "band": target.get("band"),
            "price_usd": target.get("price_usd"),
            "url": target["url"],
            "rating_value": target.get("rating_value"),
            "review_source": target.get("review_source"),
            "review_score": target.get("review_score"),
        },
        "peer_count": len(rows),
        "rows": rows,
        "axis_tally": {axis: dict(counts) for axis, counts in tally.items()},
        "strengths": strengths,
        "weaknesses": weaknesses,
    }


# ── 주기 실행 (감시 목록) ──────────────────────────────────────────────
def list_watches() -> list[dict]:
    return store.list("watch")


def add_watch(region: str, category: str, makers: list[str] | None = None, every_hours: int = 168) -> dict:
    if region not in catalog.REGIONS or category not in catalog.CATEGORIES:
        raise ValueError("대륙이나 품목 이름이 올바르지 않습니다.")
    return store.put(
        "watch",
        {
            "region": region,
            "category": category,
            "makers": makers or [],
            "every_hours": max(1, int(every_hours)),
            "last_run": "",
            "last_result": "",
        },
    )


def delete_watch(watch_id: str) -> bool:
    return store.delete(watch_id)


def _due(watch: dict) -> bool:
    if not watch.get("last_run"):
        return True
    last = datetime.fromisoformat(watch["last_run"])
    return datetime.now(timezone.utc) - last >= timedelta(hours=watch.get("every_hours", 168))


def run_watch(watch_id: str) -> dict:
    watch = store.get(watch_id)
    if not watch:
        return {"ok": False, "error": "없는 감시 항목입니다."}
    result = scan(watch["region"], watch["category"], watch.get("makers") or None)
    summary = (
        f"제품 {result.get('product_count', 0)}개, 신제품 {result.get('new_count', 0)}개"
        if result.get("ok")
        else result.get("error", "실패")
    )
    store.update(watch_id, last_run=now_iso(), last_result=summary)
    return {**result, "watch_id": watch_id, "summary": summary}


def run_due_watches() -> list[dict]:
    """때가 된 감시 항목을 모두 돌립니다. 플랫폼 예약에서 불러도 됩니다."""
    return [run_watch(w["id"]) for w in list_watches() if _due(w)]


def start_background_scheduler() -> None:
    """앱 안에서 CHECK 간격마다 감시 목록을 확인해 때가 된 것을 돌립니다.

    WATCH_SCHEDULER=false 로 끄면 플랫폼의 '예약' 화면에서
    run_due_watches 를 부르는 방식으로만 돌립니다.
    """
    if os.getenv("WATCH_SCHEDULER", "true").lower() != "true":
        return
    interval = int(os.getenv("WATCH_CHECK_SECONDS", "600"))

    def loop() -> None:
        while True:
            time.sleep(interval)
            try:
                run_due_watches()
            except Exception as exc:  # 한 번 실패해도 다음 번은 돌아야 합니다
                print(f"[appliance_watch] 주기 실행 실패: {exc}", flush=True)

    threading.Thread(target=loop, name="appliance-watch-scheduler", daemon=True).start()
