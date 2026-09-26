"""인터넷에서 페이지를 받아오는 곳. 예의 바르게 받는 규칙이 여기 다 모여 있습니다.

- 사이트가 robots.txt 로 "여기는 긁지 마세요" 한 곳은 받지 않습니다.
- 같은 사이트에는 CRAWL_DELAY 초 간격을 두고 요청합니다(서버에 부담 주지 않게).
- 받아 온 페이지는 잠깐(CACHE_SECONDS) 기억해 두고 같은 주소를 또 받지 않습니다.
- 보통 요청(httpx)이 401/403/429/503 으로 막히면(예: GE 사이트의 Akamai 봇 차단),
  진짜 브라우저(Playwright)로 한 번 더 열어 봅니다. 브라우저는 요청 하나마다
  새로 띄우고 바로 닫아서, 못 쓰는 자리(캐시가 안 되는 주소 등)에는 최소한으로만 씁니다.
  Playwright 가 안 깔려 있으면 조용히 원래 실패 이유를 그대로 보여줍니다.

테스트에서는 fetch_text 를 바꿔 끼워 인터넷 없이 돌립니다.
"""
from __future__ import annotations

import os
import threading
import time
from urllib import robotparser
from urllib.parse import urlparse

import httpx

USER_AGENT = os.getenv(
    "CRAWLER_USER_AGENT",
    "Mozilla/5.0 (compatible; WorkflowAutoApplianceWatch/1.0; market research)",
)
TIMEOUT = float(os.getenv("CRAWL_TIMEOUT", "20"))
CRAWL_DELAY = float(os.getenv("CRAWL_DELAY", "1.0"))
CACHE_SECONDS = float(os.getenv("CRAWL_CACHE_SECONDS", "900"))
# 회사 프록시를 거쳐야 하면 .env 에 HTTPS_PROXY 를 넣으세요. httpx 가 알아서 씁니다.

# 봇 차단으로 흔히 쓰이는 상태 코드. 이럴 때만 브라우저로 다시 시도합니다
# (404 같은 "그냥 없는 페이지"는 브라우저로 열어봐야 소용없으니 건너뜁니다).
_BLOCK_STATUSES = {401, 403, 429, 503}
BROWSER_FETCH = os.getenv("BROWSER_FETCH_FALLBACK", "true").lower() == "true"
BROWSER_TIMEOUT = float(os.getenv("BROWSER_FETCH_TIMEOUT", str(TIMEOUT * 2)))

_lock = threading.Lock()
_last_hit: dict[str, float] = {}
_robots: dict[str, robotparser.RobotFileParser | None] = {}
_cache: dict[str, tuple[float, str]] = {}


class FetchError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _client() -> httpx.Client:
    return httpx.Client(
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-US,en;q=0.8,ko;q=0.6",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        timeout=TIMEOUT,
        follow_redirects=True,
    )


def _raw_get(url: str) -> str:
    with _client() as client:
        response = client.get(url)
    if response.status_code >= 400:
        raise FetchError(f"{response.status_code} {url}", status_code=response.status_code)
    return response.text


def _fetch_via_browser(url: str) -> str:
    """일반 요청이 막힌 주소를 진짜 브라우저로 열어 HTML 을 받아옵니다.

    pip install playwright && playwright install chromium 이 되어 있어야 동작합니다.
    (requirements.txt 에 playwright 가 있지만, 브라우저 실행 파일은 별도 설치가 필요합니다.)
    """
    from playwright.sync_api import sync_playwright  # 안 깔려 있으면 여기서 ImportError

    with sync_playwright() as pw:
        # 브라우저 실행 파일 경로를 미리 정해 둔 곳(예: 사내 표준 이미지)이 있으면
        # CHROMIUM_EXECUTABLE_PATH 로 지정할 수 있습니다. 비워 두면 Playwright 가
        # `playwright install` 로 받아 둔 기본 위치를 씁니다.
        executable_path = os.getenv("CHROMIUM_EXECUTABLE_PATH", "").strip() or None
        browser = pw.chromium.launch(
            args=["--ignore-certificate-errors"], executable_path=executable_path
        )
        try:
            context = browser.new_context(
                ignore_https_errors=True, user_agent=USER_AGENT, locale="en-US"
            )
            try:
                page = context.new_page()
                response = page.goto(url, wait_until="domcontentloaded", timeout=BROWSER_TIMEOUT * 1000)
                status = response.status if response else None
                if response is None or status >= 400:
                    raise FetchError(f"{status or '???'} {url} (브라우저로도 막혔습니다)", status_code=status)
                return page.content()
            finally:
                context.close()
        finally:
            browser.close()


def _get_with_fallback(url: str) -> str:
    try:
        return _raw_get(url)
    except FetchError as exc:
        if not BROWSER_FETCH or exc.status_code not in _BLOCK_STATUSES:
            raise
        try:
            return _fetch_via_browser(url)
        except Exception:
            raise exc from None  # 브라우저도 안 되면 원래 막힌 이유를 그대로 보여줍니다


def _wait_turn(host: str) -> None:
    with _lock:
        gap = CRAWL_DELAY - (time.monotonic() - _last_hit.get(host, 0.0))
        _last_hit[host] = time.monotonic() + max(gap, 0.0)
    if gap > 0:
        time.sleep(gap)


def allowed(url: str) -> bool:
    """robots.txt 가 이 주소를 허락하는지. robots.txt 를 못 받으면 허락으로 봅니다."""
    parts = urlparse(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    if origin not in _robots:
        parser: robotparser.RobotFileParser | None = robotparser.RobotFileParser()
        try:
            parser.parse(fetch_text(f"{origin}/robots.txt", check_robots=False).splitlines())
        except Exception:
            parser = None
        _robots[origin] = parser
    parser = _robots[origin]
    return True if parser is None else parser.can_fetch(USER_AGENT, url)


def robots_sitemaps(origin: str) -> list[str]:
    """robots.txt 에 적힌 사이트맵 주소들."""
    try:
        text = fetch_text(f"{origin}/robots.txt", check_robots=False)
    except Exception:
        return []
    return [
        line.split(":", 1)[1].strip()
        for line in text.splitlines()
        if line.lower().startswith("sitemap:")
    ]


def fetch_text(url: str, check_robots: bool = True) -> str:
    """주소의 내용을 글자로 받아옵니다. 막힌 주소면 FetchError."""
    now = time.monotonic()
    cached = _cache.get(url)
    if cached and now - cached[0] < CACHE_SECONDS:
        return cached[1]
    if check_robots and not allowed(url):
        raise FetchError(f"robots.txt 가 막은 주소입니다: {url}")
    _wait_turn(urlparse(url).netloc)
    try:
        text = _get_with_fallback(url)
    except httpx.HTTPError as exc:
        raise FetchError(f"{url}: {exc}") from exc
    _cache[url] = (time.monotonic(), text)
    return text


def reset() -> None:
    """테스트용: 기억해 둔 것을 전부 잊습니다."""
    _cache.clear()
    _robots.clear()
    _last_hit.clear()
