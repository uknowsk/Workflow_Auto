"""POD(Point of Difference, 차별점) 뽑기.

"이 제품만의 내세울 점"은 혼자 봐서는 모릅니다. 같은 품목·같은 가격대의
경쟁 제품과 나란히 놓고 "남들은 없는데 이것만 있는 것"을 골라야 합니다.

- 사내 LLM(Gauss 등)이 연결돼 있으면: 제품 특징 + 경쟁 제품 요약을 주고 POD 3개를 받습니다.
- 연결이 안 돼 있거나 실패하면: 특징 문장 중에서 경쟁 제품들에는 잘 안 나오는
  낱말이 많은 문장을 고릅니다(드물수록 차별점일 가능성이 높다는 단순한 규칙).
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


def _peer_digest(peers: list[dict]) -> str:
    rows = []
    for peer in peers[:8]:
        feats = "; ".join(_lines(peer)[:4])
        rows.append(f"- {peer.get('maker', '')} {peer.get('name', '')}: {feats}")
    return "\n".join(rows) or "(비교할 경쟁 제품 없음)"


def llm_pods(product: dict, peers: list[dict], limit: int = 3) -> list[str] | None:
    """LLM 으로 POD 를 뽑습니다. 연결이 없거나 실패하면 None."""
    if not (POD_USE_LLM and LLM_BASE_URL):
        return None
    try:
        from openai import OpenAI

        client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY, timeout=LLM_TIMEOUT)
        specs = "; ".join(f"{k}: {v}" for k, v in list((product.get("specs") or {}).items())[:25])
        prompt = (
            f"제품: {product.get('maker', '')} {product.get('name', '')} ({product.get('model', '')})\n"
            f"가격: {product.get('price')} {product.get('currency')}\n"
            f"특징: {' / '.join(_lines(product)[:10])}\n스펙: {specs}\n\n"
            f"같은 품목의 경쟁 제품:\n{_peer_digest(peers)}\n\n"
            f"경쟁 제품과 비교했을 때 이 제품만의 차별점(POD)을 한국어로 {limit}개 뽑아라. "
            "페이지에 근거가 있는 것만 쓰고, 숫자는 그대로 살려라. "
            'JSON 으로만 답해라. 형식: {"pods": ["...", "..."]}'
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
        pods = json.loads(match.group(0)).get("pods", []) if match else []
        return [str(p).strip() for p in pods if str(p).strip()][:limit] or None
    except Exception:
        return None


def extract_pods(product: dict, peers: list[dict], limit: int = 3) -> tuple[list[str], str]:
    """(POD 목록, 어떻게 뽑았는지) 를 돌려줍니다."""
    pods = llm_pods(product, peers, limit)
    if pods:
        return pods, "llm"
    return heuristic_pods(product, peers, limit), "rule"
