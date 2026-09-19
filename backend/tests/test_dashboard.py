"""대시보드가 앱의 JSON 답을 사람이 읽을 수 있는 줄로 바꾸는지."""
from app.api.dashboard import summarize


def test_할_일_목록을_한_줄씩_보여준다():
    text = summarize(
        '{"count": 2, "tasks": ['
        '{"title": "규격 확정", "owner": "관리자", "due": "2026-09-21", "days_left": 2},'
        '{"title": "보고서 검토", "owner": "관리자", "due": "2026-09-20", "days_left": 0}]}'
    )
    assert text.splitlines() == [
        "규격 확정 · 관리자 · 2026-09-21까지 · 2일 남음",
        "보고서 검토 · 관리자 · 2026-09-20까지 · 오늘 마감",
    ]


def test_기한이_지났으면_지났다고_적는다():
    assert "3일 지남" in summarize('{"tasks": [{"title": "제출", "days_left": -3}]}')


def test_빈_목록은_빈_글자라서_화면이_빈_칸으로_바뀐다():
    assert summarize('{"count": 0, "tasks": []}') == ""


def test_개수만_세는_칸은_목록으로_오해하지_않는다():
    # count 같은 숫자 칸이 아니라 진짜 목록을 골라야 합니다.
    text = summarize('{"count": 1, "people": [{"subject": "회신 요청", "to_name": "최바다"}]}')
    assert text == "회신 요청 · 최바다"


def test_너무_길면_뒤는_몇_건_남았는지만_적는다():
    rows = ",".join(f'{{"title": "할 일 {i}"}}' for i in range(10))
    text = summarize('{"tasks": [' + rows + "]}")
    assert len(text.splitlines()) == 7
    assert text.splitlines()[-1] == "… 외 4건"


def test_모르는_모양이면_받은_그대로_둔다():
    # 앱이 JSON 이 아닌 글을 돌려줄 수도 있습니다. 그때는 손대지 않습니다.
    assert summarize("오늘은 처리할 것이 없습니다.") == "오늘은 처리할 것이 없습니다."
    assert summarize('{"ok": true}') == '{"ok": true}'
