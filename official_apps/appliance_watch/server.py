"""가전 신제품 조사 앱 - 대륙별 탑 5 가전사의 품목별 신제품을 찾아 가격대별로 정리합니다.

한 프로세스가 두 가지를 같이 띄웁니다.
  /mcp   - 오케스트레이터가 부르는 MCP 주소 ("북미 조리기기 신제품 조사해줘")
  /api/* - 화면(/appliances)이 부르는 주소 (고르고, 누르고, 비교하는 화면)

이 앱은 바깥 인터넷(제조사 홈페이지)에 나가야 합니다. 폐쇄망이면 .env 에
HTTPS_PROXY 를 넣거나, 인터넷이 되는 서버에서 따로 띄우세요.

실행:  PORT=9119 python -m appliance_watch.server   ->  http://localhost:9119/mcp
"""

import os

from mcp.server.fastmcp import FastMCP
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import service

mcp = FastMCP(
    "가전 신제품 조사",
    instructions=(
        "대륙별 탑 5 가전사의 품목별 신제품을 공식 홈페이지에서 찾아 가격, POD(차별점), "
        "제품 스펙을 정리하고 가격대별로 비교합니다."
    ),
    host=os.getenv("HOST", "0.0.0.0"),
    port=int(os.getenv("PORT", "9119")),
)

def _brief(product: dict) -> dict:
    """오케스트레이터에게 돌려줄 때는 긴 스펙을 줄여서."""
    specs = product.get("specs") or {}
    return {
        "maker": product.get("maker"),
        "name": product.get("name"),
        "model": product.get("model"),
        "price": product.get("price"),
        "currency": product.get("currency"),
        "price_usd": product.get("price_usd"),
        "band": product.get("band"),
        "is_new": product.get("is_new"),
        "new_reason": product.get("new_reason"),
        "pods": product.get("pods", []),
        "key_specs": dict(list(specs.items())[:8]),
        "url": product.get("url"),
    }


# ── MCP 기능 (오케스트레이터용) ────────────────────────────────────────
@mcp.tool()
def list_catalog() -> dict:
    """조사할 수 있는 대륙, 대륙별 탑 5 제조사, 품목, 품목별 가격대 구간을 보여 줍니다."""
    return service.catalog_view()


@mcp.tool()
def scan_new_products(region: str, category: str, makers: str = "", max_per_maker: int = 0) -> dict:
    """대륙과 품목을 골라 탑 5 제조사 홈페이지에서 신제품을 찾아 가격·POD·스펙을 정리해 저장합니다.

    Args:
        region: 대륙. north_america(북아메리카), europe(유럽), asia(아시아),
            south_america(남아메리카), oceania(오세아니아)
        category: 품목. cooking(조리기기), refrigerator(냉장고), laundry(세탁기·건조기),
            dishwasher(식기세척기), air(에어컨·공기청정), vacuum(청소기)
        makers: 일부 회사만 볼 때 쉼표로. 예) "GE Appliances,Whirlpool". 비우면 탑 5 전부
        max_per_maker: 회사당 최대 제품 수. 0 이면 기본값(8)
    """
    names = [m.strip() for m in makers.split(",") if m.strip()]
    result = service.scan(region, category, names or None, max_per_maker)
    if result.get("ok"):
        result["products"] = [_brief(p) for p in result["products"]]
    return result


@mcp.tool()
def compare_by_price(region: str = "", category: str = "cooking", mode: str = "fixed", only_new: bool = False) -> dict:
    """저장된 제품을 가격대(보급형·중급형·프리미엄·최고급)로 나눠 비교합니다.

    Args:
        region: 대륙. 비우면 모든 대륙을 달러로 환산해 함께 비교
        category: 품목
        mode: fixed(품목별 달러 기준) 또는 quantile(고른 제품 안에서 4등분)
        only_new: true 면 신제품만
    """
    result = service.compare(region, category, mode=mode, only_new=only_new)
    for band in result["bands"]:
        band["products"] = [_brief(p) for p in band["products"]]
    result["unpriced"] = [_brief(p) for p in result["unpriced"]]
    return result


@mcp.tool()
def list_products(region: str = "", category: str = "", maker: str = "", only_new: bool = False) -> dict:
    """지금까지 모아 둔 제품을 싼 순서로 보여 줍니다."""
    items = service.list_products(region, category, maker, only_new=only_new)
    return {"count": len(items), "products": [_brief(p) for p in items]}


@mcp.tool()
def list_sources(region: str = "", category: str = "", maker: str = "") -> dict:
    """앱이 스스로 찾아낸 '제품 정보가 올라오는 곳'(사이트맵, 목록 페이지, 검색) 목록과 점수."""
    items = service.list_sources(region, category, maker)
    return {"count": len(items), "sources": items}


@mcp.tool()
def add_source(maker: str, region: str, category: str, url: str) -> dict:
    """자동으로 못 찾을 때, 제품 목록 페이지나 제품 페이지 주소를 직접 알려 줍니다."""
    return {"ok": True, "source": service.add_source(maker, region, category, url)}


@mcp.tool()
def set_region_makers(region: str, makers: str) -> dict:
    """대륙별 탑 5 제조사를 바꿉니다.

    Args:
        region: 대륙
        makers: "이름|홈페이지" 를 쉼표로. 예) "GE Appliances|https://www.geappliances.com,Whirlpool|"
    """
    parsed = []
    for item in makers.split(","):
        name, _, site = item.partition("|")
        parsed.append({"name": name, "site": site})
    return {"ok": True, "makers": service.set_region_makers(region, parsed)}


@mcp.tool()
def add_watch(region: str, category: str, makers: str = "", every_hours: int = 168) -> dict:
    """주기적으로 신제품을 확인할 대상을 등록합니다. 기본은 일주일(168시간)마다."""
    names = [m.strip() for m in makers.split(",") if m.strip()]
    return {"ok": True, "watch": service.add_watch(region, category, names, every_hours)}


@mcp.tool()
def run_due_watches() -> dict:
    """때가 된 감시 항목을 지금 돌립니다. 플랫폼 '예약'에 걸어 두기 좋은 기능입니다."""
    results = service.run_due_watches()
    return {"ran": len(results), "results": [{"watch_id": r["watch_id"], "summary": r["summary"]} for r in results]}


# ── 화면용 주소 ───────────────────────────────────────────────────────
async def _body(request: Request) -> dict:
    try:
        data = await request.json()
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _makers_param(value) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    return [v.strip() for v in str(value or "").split(",") if v.strip()]


@mcp.custom_route("/api/catalog", methods=["GET"])
async def api_catalog(request: Request):
    return JSONResponse(service.catalog_view())


@mcp.custom_route("/api/makers", methods=["POST"])
async def api_set_makers(request: Request):
    body = await _body(request)
    try:
        makers = service.set_region_makers(body.get("region", ""), body.get("makers") or [])
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    return JSONResponse({"ok": True, "makers": makers})


@mcp.custom_route("/api/scan", methods=["POST"])
async def api_scan(request: Request):
    import anyio

    body = await _body(request)
    # 조사는 오래 걸리므로(사이트마다 여러 페이지) 다른 요청을 막지 않게 따로 돌립니다.
    result = await anyio.to_thread.run_sync(
        lambda: service.scan(
            body.get("region", ""),
            body.get("category", ""),
            _makers_param(body.get("makers")) or None,
            int(body.get("max_per_maker") or 0),
        )
    )
    return JSONResponse(result, status_code=200 if result.get("ok") else 400)


@mcp.custom_route("/api/products", methods=["GET"])
async def api_products(request: Request):
    q = request.query_params
    items = service.list_products(
        q.get("region", ""), q.get("category", ""), q.get("maker", ""), q.get("band", ""),
        q.get("only_new", "") == "true",
    )
    return JSONResponse({"count": len(items), "products": items})


@mcp.custom_route("/api/compare", methods=["GET"])
async def api_compare(request: Request):
    q = request.query_params
    result = service.compare(
        q.get("region", ""),
        q.get("category", "cooking"),
        _makers_param(q.get("makers")),
        q.get("mode", "fixed"),
        q.get("only_new", "") == "true",
    )
    return JSONResponse(result)


@mcp.custom_route("/api/sources", methods=["GET", "POST"])
async def api_sources(request: Request):
    if request.method == "POST":
        body = await _body(request)
        if not str(body.get("url", "")).startswith("http"):
            return JSONResponse({"ok": False, "error": "http 로 시작하는 주소를 넣어 주세요."}, status_code=400)
        source = service.add_source(body.get("maker", ""), body.get("region", ""), body.get("category", ""), body["url"])
        return JSONResponse({"ok": True, "source": source})
    q = request.query_params
    items = service.list_sources(q.get("region", ""), q.get("category", ""), q.get("maker", ""))
    return JSONResponse({"count": len(items), "sources": items})


@mcp.custom_route("/api/scans", methods=["GET"])
async def api_scans(request: Request):
    return JSONResponse({"scans": service.recent_scans()})


@mcp.custom_route("/api/watches", methods=["GET", "POST"])
async def api_watches(request: Request):
    if request.method == "POST":
        body = await _body(request)
        try:
            watch = service.add_watch(
                body.get("region", ""),
                body.get("category", ""),
                _makers_param(body.get("makers")),
                int(body.get("every_hours") or 168),
            )
        except ValueError as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
        return JSONResponse({"ok": True, "watch": watch})
    return JSONResponse({"watches": service.list_watches()})


@mcp.custom_route("/api/watches/{watch_id}", methods=["DELETE"])
async def api_delete_watch(request: Request):
    return JSONResponse({"ok": service.delete_watch(request.path_params["watch_id"])})


@mcp.custom_route("/api/watches/{watch_id}/run", methods=["POST"])
async def api_run_watch(request: Request):
    import anyio

    watch_id = request.path_params["watch_id"]
    result = await anyio.to_thread.run_sync(lambda: service.run_watch(watch_id))
    return JSONResponse(result, status_code=200 if result.get("ok") else 400)


@mcp.custom_route("/api/health", methods=["GET"])
async def api_health(request: Request):
    return JSONResponse({"status": "ok", "app": "appliance-watch"})


def build_app():
    app = mcp.streamable_http_app()
    # 화면(3000번)에서 바로 부를 수 있게 열어 둡니다. 사내 배포 시 실제 화면 주소로 좁히세요.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("ALLOW_ORIGINS", "*").split(","),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app


if __name__ == "__main__":
    import uvicorn

    service.start_background_scheduler()
    uvicorn.run(build_app(), host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "9119")))
