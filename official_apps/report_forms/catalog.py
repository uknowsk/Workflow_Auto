"""보고서 종류와 분량 정의 — 이 앱의 '내용물'이 전부 여기 모여 있습니다.

코드를 고치지 않고 회사 실정에 맞추려면 이 파일의 표만 손보면 됩니다.

section 의 level 은 "몇 장짜리 보고서부터 이 항목이 들어가는가" 입니다.
  1 = 한 장 요약에도 반드시 들어가는 항목 (결론 위주)
  2 = 표준(3장)부터 들어가는 항목
  3 = 상세 보고서에만 들어가는 항목
윗분들이 먼저 보는 것부터 적는 두괄식이라, 배경보다 결론이 앞에 옵니다.
"""
from __future__ import annotations

# 분량 3단계. levels 는 위에서 설명한 level 을 어디까지 넣을지입니다.
LENGTHS: dict[str, dict] = {
    "1장": {"levels": 1, "hint": "핵심만. 결론 → 근거 순서로 한 장에 끝냅니다."},
    "3장": {"levels": 2, "hint": "표준 분량. 배경·경과·결과를 갖춘 일반적인 보고서입니다."},
    "상세": {"levels": 3, "hint": "근거 자료와 후속 계획까지 모두 담는 긴 보고서입니다."},
}
DEFAULT_LENGTH = "3장"

# 어느 보고서에나 들어가는 머리부. (라벨, 값을 넣을 때 쓰는 이름)
HEADER_FIELDS: list[tuple[str, str]] = [
    ("보고 일자", "reported_on"),
    ("작성자", "author"),
    ("소속", "dept"),
    ("지시자", "ordered_by"),
    ("지시 일자", "ordered_on"),
    ("제출 기한", "due_on"),
]


def _s(key: str, title: str, guide: str, level: int) -> dict:
    return {"key": key, "title": title, "guide": guide, "level": level}


REPORT_TYPES: dict[str, dict] = {
    "검토보고": {
        "when": "지시받은 안건을 따져 보고 의견이나 대안을 올릴 때",
        "example": "「A 설비 도입 타당성 검토해서 보고」",
        "sections": [
            _s("conclusion", "검토 결론", "결론 한 문장 먼저. 예) 도입이 타당하며 3분기 착수를 건의합니다.", 1),
            _s("background", "검토 배경", "무엇을 왜 검토하게 됐는지, 지시 내용과 배경을 2~3줄로.", 1),
            _s("request", "건의 사항", "윗분이 결정해 주셔야 하는 것만 항목으로.", 1),
            _s("detail", "검토 내용", "쟁점별로 나눠 사실과 판단을 구분해 적습니다.", 2),
            _s("options", "대안 비교", "대안 2~3개를 장단점·비용·기간으로 비교한 표.", 2),
            _s("effect", "기대 효과", "정량(금액·시간·불량률)을 먼저, 정성은 뒤에.", 2),
            _s("basis", "관련 근거·규정", "인용한 규정, 지침, 사내 기준의 조항 번호까지.", 3),
            _s("cases", "타부서·타사 사례", "비슷한 사례와 그 결과. 우리와 다른 조건도 같이.", 3),
            _s("plan", "향후 일정", "승인 이후 무엇을 언제까지 하는지.", 3),
            _s("attach", "첨부", "붙임 자료 목록.", 3),
        ],
    },
    "결과보고": {
        "when": "지시받은 일을 끝내고 무엇을 어떻게 했는지 보고할 때",
        "example": "「지난달 지시한 설비 점검 결과 보고」",
        "sections": [
            _s("summary", "추진 결과", "결론 먼저. 목표 대비 무엇을 달성했는지 한 문장.", 1),
            _s("overview", "추진 개요", "기간, 대상, 목표, 투입 인원을 짧게.", 1),
            _s("next", "향후 계획", "남은 일과 후속 조치, 담당과 기한.", 1),
            _s("progress", "추진 경과", "일정별로 무엇을 했는지. 표가 읽기 좋습니다.", 2),
            _s("outcome", "주요 성과", "숫자로 말합니다. 전/후 비교가 가장 잘 먹힙니다.", 2),
            _s("gap", "미흡 사항", "못 한 것과 그 이유, 보완 방안.", 2),
            _s("resource", "투입 자원", "인력·예산·설비 집행 내역.", 3),
            _s("lesson", "문제점 및 개선 사항", "다음에 같은 일을 할 사람이 볼 교훈.", 3),
            _s("attach", "참고 자료", "붙임 자료 목록.", 3),
        ],
    },
    "출장보고": {
        "when": "국내외 출장·현장 방문을 다녀와 보고할 때",
        "example": "「평택 협력사 방문 결과 보고」",
        "sections": [
            _s("overview", "출장 개요", "일시, 장소, 목적, 동행자를 한 칸에 모아서.", 1),
            _s("main", "주요 내용", "무엇을 보고 무엇을 협의했는지 결론 위주로.", 1),
            _s("action", "조치 필요 사항", "우리 부서가 해야 할 일과 담당·기한.", 1),
            _s("daily", "일자별 활동", "날짜 → 방문처 → 내용 순으로.", 2),
            _s("meeting", "면담·협의 결과", "누구와 무엇을 합의했고 무엇이 보류됐는지.", 2),
            _s("insight", "시사점", "우리 업무에 어떤 의미가 있는지.", 2),
            _s("cost", "비용 정산", "항목별 금액과 증빙 여부.", 3),
            _s("materials", "수집 자료", "받아 온 자료 목록과 보관 위치.", 3),
            _s("followup", "후속 일정", "다음 접촉·방문 예정.", 3),
        ],
    },
    "현황보고": {
        "when": "진행 중인 일의 진도를 주기적으로 보고할 때",
        "example": "「이번 주 구축 진도 보고」",
        "sections": [
            _s("summary", "전체 진도", "예) 계획 대비 82%, 2일 지연. 숫자 하나로 먼저.", 1),
            _s("done", "이번 기간 실적", "이번 주(달)에 끝낸 일만.", 1),
            _s("plan", "다음 기간 계획", "다음 주(달)에 할 일과 담당.", 1),
            _s("table", "항목별 진도", "항목 / 계획 / 실적 / 진도율 표.", 2),
            _s("delay", "지연 항목 및 사유", "지연된 것만 따로. 사유와 만회 방안까지.", 2),
            _s("risk", "리스크·이슈", "터지기 전에 알려야 할 것. 영향도와 대응.", 2),
            _s("resource", "인력·예산 집행", "계획 대비 집행률.", 3),
            _s("help", "협조 요청", "다른 부서나 윗선의 도움이 필요한 것.", 3),
            _s("schedule", "상세 일정표", "전체 일정과 현재 위치.", 3),
        ],
    },
    "이슈보고": {
        "when": "장애·사고·품질 문제가 터져 급히 보고할 때",
        "example": "「생산라인 정지 발생 보고」",
        "sections": [
            _s("what", "발생 개요", "언제, 어디서, 무엇이. 감정 빼고 사실만.", 1),
            _s("impact", "영향 범위", "누가·무엇이 얼마나 영향을 받는지. 금액·시간으로.", 1),
            _s("status", "조치 현황", "지금 무엇을 하고 있고 언제 정상화되는지.", 1),
            _s("cause", "원인 분석", "직접 원인과 근본 원인을 나눠서.", 2),
            _s("timeline", "경과", "시각 → 상황 → 조치 순의 시간대별 기록.", 2),
            _s("prevent", "재발 방지 대책", "대책 / 담당 / 완료 기한 세 가지가 꼭 같이.", 2),
            _s("similar", "유사 사례", "과거에 같은 일이 있었는지.", 3),
            _s("coop", "관련 부서 협의", "협의 내용과 각 부서 역할.", 3),
            _s("check", "후속 점검 계획", "언제 다시 확인할지.", 3),
        ],
    },
    "회의결과보고": {
        "when": "회의·워크숍 결과를 정리해 보고할 때",
        "example": "「월간 품질회의 결과 보고」",
        "sections": [
            _s("overview", "회의 개요", "일시, 장소, 참석자, 안건.", 1),
            _s("decision", "주요 결정 사항", "결정된 것만 번호를 붙여서.", 1),
            _s("action", "후속 조치", "할 일 / 담당 / 기한 표. 이게 회의록의 핵심입니다.", 1),
            _s("discussion", "논의 내용", "안건별로 오간 이야기를 요약.", 2),
            _s("pending", "이견·보류 사항", "결론이 안 난 것과 다음에 다룰 시점.", 2),
            _s("remarks", "발언 요지", "누가 어떤 취지로 말했는지(필요할 때만).", 3),
            _s("share", "배포처", "이 보고서를 받아야 할 사람들.", 3),
            _s("attach", "첨부 자료", "발표 자료, 회의 사진 등.", 3),
        ],
    },
}

# 요청문에 이런 말이 있으면 이 종류를 추천합니다. 위에서부터 먼저 맞는 것을 씁니다.
KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("이슈보고", ("장애", "사고", "정지", "불량", "클레임", "긴급", "이슈", "오류", "결함")),
    ("출장보고", ("출장", "방문", "현장", "견학", "파견", "해외")),
    ("회의결과보고", ("회의", "미팅", "워크숍", "간담회", "협의체")),
    ("현황보고", ("진도", "현황", "주간", "월간", "진척", "경과 보고", "중간")),
    ("결과보고", ("완료", "결과", "실적", "마무리", "종료", "성과")),
    ("검토보고", ("검토", "타당성", "방안", "대안", "도입", "개선안", "의견")),
]


# 사람들이 실제로 쓰는 다른 이름들. 왼쪽으로 불러도 오른쪽 종류로 알아듣습니다.
ALIASES: dict[str, str] = {
    "진도보고": "현황보고",
    "중간보고": "현황보고",
    "주간보고": "현황보고",
    "월간보고": "현황보고",
    "완료보고": "결과보고",
    "실적보고": "결과보고",
    "사고보고": "이슈보고",
    "장애보고": "이슈보고",
    "품질이슈": "이슈보고",
    "회의록": "회의결과보고",
    "타당성검토": "검토보고",
}


def resolve_type(name: str) -> str:
    """'검토', '검토 보고서', '진도보고' 처럼 적어도 알아듣게 합니다. 모르면 빈 문자열.

    긴 이름부터 맞춰 봅니다 — 그래야 '회의결과보고' 가 '결과보고' 로 잘못 잡히지 않습니다.
    """
    cleaned = (name or "").replace(" ", "")
    if not cleaned:
        return ""
    if cleaned in REPORT_TYPES:
        return cleaned
    if cleaned in ALIASES:
        return ALIASES[cleaned]
    trimmed = cleaned.replace("보고서", "보고")
    for key in sorted(REPORT_TYPES, key=len, reverse=True):
        stem = key.replace("보고", "")
        if key in trimmed or trimmed == stem:
            return key
    for alias, key in sorted(ALIASES.items(), key=lambda kv: len(kv[0]), reverse=True):
        if alias in trimmed:
            return key
    for key in sorted(REPORT_TYPES, key=len, reverse=True):
        stem = key.replace("보고", "")
        if stem and stem in trimmed:
            return key
    return ""


def resolve_length(name: str) -> str:
    """'1장', '한장', '요약' / '3장', '표준' / '상세', '전체' 를 받아 줍니다."""
    cleaned = (name or "").replace(" ", "")
    if not cleaned:
        return DEFAULT_LENGTH
    if cleaned in LENGTHS:
        return cleaned
    if any(word in cleaned for word in ("1", "한", "요약", "간단", "짧")):
        return "1장"
    if any(word in cleaned for word in ("상세", "전체", "자세", "길")):
        return "상세"
    return DEFAULT_LENGTH


def sections_for(report_type: str, length: str) -> list[dict]:
    """고른 종류·분량에 들어갈 항목만 골라 돌려줍니다."""
    limit = LENGTHS[length]["levels"]
    return [s for s in REPORT_TYPES[report_type]["sections"] if s["level"] <= limit]
