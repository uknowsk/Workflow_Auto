"""뉴스·유튜브에서 "요즘 화제인 제품"을 찾습니다.

앞의 discover.py/extract.py 는 "공식 홈페이지에 이미 올라온 제품"을 훑는
쪽이라, 아직 홈페이지에는 안 올라왔지만 언론에 먼저 보도되거나 유튜브
리뷰가 먼저 도는 신제품(예: 발표회 직후)은 놓칩니다. 이 파일은 그 빈틈을
메우는 보조 신호입니다 — 제품 페이지를 대신하지 않고, "이 회사·이 품목이
요즘 얼마나 화제인지"를 곁들이는 참고 자료로만 씁니다.

- 뉴스: Google News RSS. API 키가 필요 없어서 기본으로 켜져 있습니다.
- 유튜브: YouTube Data API. 키(YOUTUBE_API_KEY)가 있어야 하고, 없으면
  조용히 빈 목록을 돌려줍니다(이 앱의 다른 선택 기능들과 같은 원칙).

테스트에서는 _get 을 바꿔 끼워 인터넷 없이 돌립니다(web.py 의 fetch_text 를
쓰지 않는 이유는, 뉴스·유튜브는 "예의 바르게 천천히" 규칙이 필요한 제조사
홈페이지가 아니라 그때그때 최신 결과가 중요한 별개의 출처라서입니다).
"""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET

import httpx

NEWS_ENABLED = os.getenv("TREND_NEWS_ENABLED", "true").lower() == "true"
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
TIMEOUT = float(os.getenv("TREND_TIMEOUT", "10"))

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"
YOUTUBE_SEARCH_API = "https://www.googleapis.com/youtube/v3/search"


def _get(url: str, params: dict) -> httpx.Response:
    """실제 요청 한 곳. 테스트에서 이 함수만 바꿔 끼우면 됩니다."""
    return httpx.get(url, params=params, timeout=TIMEOUT)


def fetch_google_news(query: str, limit: int = 5) -> list[dict]:
    """Google News RSS 로 최근 기사 제목·링크·날짜를 가져옵니다. 실패하면 빈 목록."""
    if not NEWS_ENABLED:
        return []
    try:
        response = _get(GOOGLE_NEWS_RSS, {"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"})
        response.raise_for_status()
        root = ET.fromstring(response.text)
    except Exception:
        return []
    items = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        source_el = item.find("source")
        source = (source_el.text or "").strip() if source_el is not None else ""
        if title and link:
            items.append({"title": title, "url": link, "published_at": pub_date, "source": source})
        if len(items) >= limit:
            break
    return items


def fetch_youtube_trends(query: str, limit: int = 5) -> list[dict]:
    """유튜브에서 최신 리뷰/소개 영상을 찾습니다. API 키가 없으면 빈 목록."""
    if not YOUTUBE_API_KEY:
        return []
    try:
        response = _get(
            YOUTUBE_SEARCH_API,
            {
                "key": YOUTUBE_API_KEY,
                "q": query,
                "part": "snippet",
                "type": "video",
                "order": "date",
                "maxResults": limit,
            },
        )
        response.raise_for_status()
        data = response.json()
    except Exception:
        return []
    items = []
    for entry in data.get("items", []):
        snippet = entry.get("snippet") or {}
        video_id = (entry.get("id") or {}).get("videoId", "")
        if not video_id:
            continue
        items.append(
            {
                "title": snippet.get("title", ""),
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "published_at": snippet.get("publishedAt", ""),
                "channel": snippet.get("channelTitle", ""),
            }
        )
    return items[:limit]


def trend_signals(maker: str, category_label: str, limit: int = 5) -> dict:
    """이 회사·이 품목에 대한 최근 뉴스·유튜브 언급을 모읍니다.

    제품 페이지를 대신하는 게 아니라("가격·모델을 뉴스에서 읽지 않습니다"),
    "요즘 이 회사가 이 품목으로 화제인지"를 곁들이는 참고 신호입니다.
    """
    query = f"{maker} {category_label} new".strip()
    news = fetch_google_news(f"{maker} {category_label}", limit)
    videos = fetch_youtube_trends(query, limit)
    return {
        "maker": maker,
        "category": category_label,
        "news": news,
        "videos": videos,
        "youtube_enabled": bool(YOUTUBE_API_KEY),
    }
