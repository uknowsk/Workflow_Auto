"""POD(Point of Difference, 차별점)·AI 기능·에너지 효율을 정리합니다.

규칙 기반 스크래핑(discover.py, extract.py)이 페이지에서 "있는 그대로"
가져온 이름·스펙·특징을 바탕으로, 여기서는 "그래서 뭐가 다른가"를 정리합니다.

- 사내 LLM(Gauss 등)이 연결돼 있으면: 제품 특징 + 경쟁 제품 요약을 한 번에 주고
  POD·AI 기능·에너지 효율을 같이 정형화해서 받습니다(llm_enrich).
- 연결이 안 돼 있거나 실패하면 규칙으로 대신합니다(heuristic_pods,
  ai_features_from_rules) — LLM 이 없어도 이 앱은 그대로 돌아갑니다.

enrich_product() 가 위 둘을 무엇을 쓸지 정하는 창구입니다.
"""
from __future__ import annotations

import json
import os
import re

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "not-needed")
LLM_MODEL = os.getenv("LLM_MODEL", "gauss")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60"))
POD_USE_LLM = os.getenv("POD_USE_LLM", "true").lower() == "true"

_WORD = re.compile(r"[a-z가-힣][a-z가-힣0-9+-]{2,}", re.I)
_STOP = {
    "the", "and", "with", "for", "your", "you", "that", "this", "from", "into", "more",
    "less", "our", "are", "all", "can", "has", "have", "its", "any", "per", "not",
}
# "OO는 최고의 가전을 만드는 회사입니다" 같은 사이트 공통 소개 문구는 이 제품만의
# 특징이 아닙니다. 숫자나 단위(용량, 와트, 인치 ...)가 있어야 제품 얘기로 봅니다.
_PRODUCT_SPECIFIC = re.compile(r"\d|cu\.?\s*ft|watt|btu|liter|inch|volt|amp|리터|인치|와트", re.I)
# AI·자동화·연결 기능. "스마트"/"자동" 처럼 너무 흔한 낱말 하나만으로는 오탐이
# 많아서, AI·음성·앱연동·사물인터넷처럼 구체적인 표현이 있어야 잡습니다.
_AI_HINT = re.compile(
    r"artificial intelligence|\bai\b|smartthings|wi-?fi|voice control|alexa|"
    r"google assistant|scan-?to-?cook|auto\s?sense|adaptive\s*(cook|sensing)|"
    r"인공지능|스마트\s?(홈|싱스)|음성\s?(인식|제어)|사물인터넷|\biot\b",
    re.I,
)


def _words(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text) if w.lower() not in _STOP}


def _lines(product: dict) -> list[str]:
    lines = list(product.get("features") or [])
    description = product.get("description") or ""
    if not lines and description and _PRODUCT_SPECIFIC.search(description):
        lines = [s.strip() for s in re.split(r"(?<=[.!?])\s+", description) if len(s) > 15]
    return lines


def heuristic_pods(product: dict, peers: list[dict], limit: int = 3) -> list[str]:
    """경쟁 제품 어디에도 안 나오는 낱말이 많은 특징 문장을 차별점으로 고릅니다."""
    lines = _lines(product)
    if not lines:
        return []
    peer_words: set[str] = set()
    for peer in peers:
        for line in _lines(peer):
            peer_words |= _words(line)

    def uniqueness(line: str) -> float:
        words = _words(line)
        if not words:
            return 0.0
        only_mine = [w for w in words if w not in peer_words]
        return len(only_mine) / len(words) * min(len(words), 8)

    ranked = sorted(lines, key=uniqueness, reverse=True)
    # 경쟁 제품도 다 말하는 특징(내 것만의 낱말이 하나도 없는 문장)은 차별점이 아닙니다.
    distinct = [line for line in ranked if uniqueness(line) > 0]
    return (distinct or ranked[:1])[:limit]


def ai_features_from_rules(product: dict, limit: int = 5) -> list[str]:
    """AI·자동화·연결 기능처럼 보이는 문장을 특징·설명에서 고릅니다(규칙 기반).

    LLM 이 없어도 "이 제품에 그런 기능이 있는지"는 알 수 있게 하는 최소한의
    안전망입니다. 지어내지 않고 페이지 문장을 그대로 가져옵니다.
    """
    return [line for line in _lines(product) if _AI_HINT.search(line)][:limit]


def _peer_digest(peers: list[dict]) -> str:
    rows = []
    for peer in peers[:8]:
        feats = "; ".join(_lines(peer)[:4])
        rows.append(f"- {peer.get('maker', '')} {peer.get('name', '')}: {feats}")
    return "\n".join(rows) or "(비교할 경쟁 제품 없음)"


def llm_enrich(product: dict, peers: list[dict], limit: int = 3) -> dict | None:
    """LLM 으로 POD·AI 기능·에너지 효율을 한 번에 정형화해서 받습니다.

    한 제품당 LLM 호출을 하나로 묶어 두는 이유는, POD 뽑으려고 한 번, AI 기능
    뽑으려고 또 한 번 부르면 그만큼 느려지고 사내 LLM 부하도 커지기 때문입니다.
    연결이 안 돼 있거나 실패하면(형식이 깨진 응답 포함) None 을 돌려주고,
    호출한 쪽(enrich_product)이 규칙 기반으로 넘어갑니다.
    """
    if not (POD_USE_LLM and LLM_BASE_URL):
        return None
    try:
        from openai import OpenAI

        client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY, timeout=LLM_TIMEOUT)
        specs = "; ".join(f"{k}: {v}" for k, v in list((product.get("specs") or {}).items())[:25])
        prompt = (
            f"제품: {product.get('maker', '')} {product.get('name', '')} ({product.get('model', '')})\n"
            f"가격: {product.get('price')} {product.get('currency')}\n"
            f"특징: {' / '.join(_lines(product)[:10])}\n스펙: {specs}\n"
            f"페이지에서 찾은 에너지 효율 단서: {product.get('energy_rating') or '(없음)'}\n\n"
            f"같은 품목의 경쟁 제품:\n{_peer_digest(peers)}\n\n"
            "페이지에 근거가 있는 것만 뽑아라(지어내지 마라). 숫자는 그대로 살려라.\n"
            f"1) pods: 경쟁 제품과 비교했을 때 이 제품만의 차별점을 한국어로 {limit}개\n"
            "2) ai_features: AI·자동화·음성제어·앱연동처럼 지능형/연결 기능이면 "
            "원문 표현 그대로 최대 5개(그런 기능이 없으면 빈 배열)\n"
            "3) energy_rating: 에너지 효율·소비전력 관련 문구가 있으면 다듬어서, "
            "없으면 빈 문자열\n"
            'JSON 으로만 답해라. 형식: {"pods": [...], "ai_features": [...], "energy_rating": "..."}'
        )
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "너는 가전 상품기획 분석가다. 없는 사실을 지어내지 마라."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        text = response.choices[0].message.content or ""
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return None
        data = json.loads(match.group(0))
        pods = [str(p).strip() for p in data.get("pods", []) if str(p).strip()][:limit]
        ai_features = [str(a).strip() for a in data.get("ai_features", []) if str(a).strip()][:5]
        energy_rating = str(data.get("energy_rating") or "").strip()
        if not pods and not ai_features and not energy_rating:
            return None  # 셋 다 비면 응답이 쓸모없다고 보고 규칙 기반으로 넘어갑니다
        return {"pods": pods, "ai_features": ai_features, "energy_rating": energy_rating}
    except Exception:
        return None


def enrich_product(product: dict, peers: list[dict], limit: int = 3) -> dict:
    """POD·AI 기능·에너지 효율을 정리해 돌려줍니다.

    돌려주는 값: {"pods", "pod_method", "ai_features", "ai_method", "energy_rating"}
    LLM 이 있으면 셋을 한 번에 정형화하고, 없거나 실패하면 항목별로 규칙 기반을
    씁니다 — LLM 이 일부만(예: POD 만) 채워 줘도 나머지는 규칙으로 채웁니다.
    energy_rating 은 페이지에서 이미 규칙으로 찾은 값이 있으면 그걸 그대로 두고,
    없을 때만 LLM 이 준 값으로 채웁니다(페이지 사실을 LLM 추측으로 덮지 않기 위해).
    """
    llm = llm_enrich(product, peers, limit) or {}
    pods = llm.get("pods") or heuristic_pods(product, peers, limit)
    pod_method = "llm" if llm.get("pods") else "rule"
    ai_features = llm.get("ai_features") or ai_features_from_rules(product)
    ai_method = "llm" if llm.get("ai_features") else "rule"
    energy_rating = product.get("energy_rating") or llm.get("energy_rating") or ""
    return {
        "pods": pods,
        "pod_method": pod_method,
        "ai_features": ai_features,
        "ai_method": ai_method,
        "energy_rating": energy_rating,
    }
