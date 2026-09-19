"""레시피의 변수 치환 테스트.

{{회의록}} 같은 자리에 값이 제대로 들어가는지, 앞 단계 결과가 다음 단계로
넘어가는지를 확인합니다. 여기가 틀리면 엉뚱한 내용으로 메일이 나갑니다.
"""
from app.orchestrator import recipe


def test_문자열_안의_변수가_바뀝니다():
    context = {"회의록": "9월 정기회의", "today": "2026-09-18"}
    assert recipe.fill("{{today}} {{회의록}} 요약", context) == "2026-09-18 9월 정기회의 요약"


def test_사전과_목록_안까지_들어갑니다():
    context = {"이름": "김로아"}
    filled = recipe.fill({"to": ["{{이름}}"], "body": {"title": "{{이름}} 님"}}, context)
    assert filled == {"to": ["김로아"], "body": {"title": "김로아 님"}}


def test_모르는_변수는_그대로_둡니다():
    """빈칸으로 만들어 버리면 값이 빠진 줄 모르고 그대로 나갑니다."""
    assert recipe.fill("{{안채운값}}", {}) == "{{안채운값}}"


def test_숫자나_참거짓은_건드리지_않습니다():
    assert recipe.fill({"days": 7, "all": True}, {}) == {"days": 7, "all": True}


def test_채워_넣어야_할_변수만_추려냅니다():
    steps = [
        {"arguments": {"text": "{{회의록}}"}},
        {"arguments": {"to": "{{담당자}}", "body": "{{step1}}", "date": "{{today}}"}},
    ]
    # step1 과 today 는 시스템이 알아서 넣으므로 빠집니다.
    assert recipe.find_variables(steps) == ["회의록", "담당자"]


def test_마무리_지시문의_변수도_함께_찾습니다():
    assert recipe.find_variables([], "{{부서}} 기준으로 정리해줘") == ["부서"]


def test_같은_변수는_한_번만_나옵니다():
    steps = [{"arguments": {"a": "{{사번}}"}}, {"arguments": {"b": "{{사번}}"}}]
    assert recipe.find_variables(steps) == ["사번"]


def test_기본_변수에는_오늘_날짜가_들어_있습니다():
    context = recipe.base_context("E1001")
    assert context["user_id"] == "E1001"
    assert len(context["today"]) == len("2026-09-18")
