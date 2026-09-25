"""인터넷에서 페이지를 받아오는 곳. 예의 바르게 받는 규칙이 여기 다 모여 있습니다.

- 사이트가 robots.txt 로 "여기는 긁지 마세요" 한 곳은 받지 않습니다.
- 같은 사이트에는 CRAWL_DELAY 초 간격을 두고 요청합니다(서버에 부담 주지 않게).
- 받아 온 페이지는 잠깐(CACHE_SECONDS) 기억해 두고 같은 주소를 또 받지 않습니다.

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

_lock = threading.Lock()
_last_hit: dict[str, float] = {}
_robots: dict[str, robotparser.RobotFileParser | None] = {}
_cache: dict[str, tuple[float, str]] = {}


class FetchError(Exception):
    pass


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
        raise FetchError(f"{response.status_code} {url}")
    return response.text


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
        text = _raw_get(url)
    except httpx.HTTPError as exc:
        raise FetchError(f"{url}: {exc}") from exc
    _cache[url] = (time.monotonic(), text)
    return text


def reset() -> None:
    """테스트용: 기억해 둔 것을 전부 잊습니다."""
    _cache.clear()
    _robots.clear()
    _last_hit.clear()
