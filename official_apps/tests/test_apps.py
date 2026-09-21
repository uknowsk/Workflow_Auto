"""앱별 핵심 동작 테스트. 오케스트레이터가 실제로 부르는 기능들입니다."""
from achievements import server as achievements
from approvals import server as approvals
from dev_projects import server as dev_projects
from meeting_scheduler import server as meeting
from toolbox import server as toolbox
from weekly_report import server as weekly


# ── 도구 모음 ───────────────────────────────────────────────────────────
def test_계산기는_사칙연산을_한다():
    assert toolbox.calculate("(100 + 20) * 2")["result"] == 240


def test_계산기는_위험한_식을_거부한다():
    result = toolbox.calculate("__import__('os').system('ls')")
    assert result["ok"] is False


def test_0으로_나누면_이유를_말한다():
    assert "0" in toolbox.calculate("1/0")["error"]


def test_단위를_바꾼다():
    assert toolbox.convert_unit(1, "kg", "g")["result"] == 1000
    assert toolbox.convert_unit(0, "c", "f")["result"] == 32


def test_모르는_단위는_쓸_수_있는_단위를_알려준다():
    result = toolbox.convert_unit(1, "말도안되는단위", "kg")
    assert result["ok"] is False and "supported" in result


def test_근무일_계산은_주말을_건너뛴다():
    # 2026-09-18 은 금요일. 근무일 1일 뒤는 다음 주 월요일이어야 합니다.
    assert toolbox.add_workdays("2026-09-18", 1)["result"] == "2026-09-21"


# ── 개발 프로젝트 ───────────────────────────────────────────────────────
def test_프로젝트를_등록하면_단계별_산출물이_따라온다():
    project = dev_projects.register_project("E-TEST", "테스트 과제", stage="설계")
    found = dev_projects.list_my_projects("E-TEST")

    assert found["count"] >= 1
    mine = [p for p in found["projects"] if p["id"] == project["id"]][0]
    assert "시스템설계서" in mine["next_deliverables"]


def test_마일스톤은_시간축_위치와_산출물을_들고_온다():
    project = dev_projects.register_project(
        "E-RTS",
        "차세대 단말",
        model="SM-X100",
        stage="설계",
        start_date="2026-01-01",
        rts_date="2026-12-31",
        milestones="설계완료 2026-03-31, 구현완료 2026-06-30 [단위시험결과서]",
    )

    assert project["model"] == "SM-X100"
    # RTS 는 시간축의 끝이라 마일스톤 줄에도 같이 보입니다.
    names = [m["name"] for m in project["milestones"]]
    assert names == ["설계완료", "구현완료", "RTS (개발완료)"]

    # 이름에 단계가 들어 있으면 그 단계의 산출물이 자동으로 따라옵니다.
    design = project["milestones"][0]
    assert [d["name"] for d in design["deliverables"]] == [
        "시스템설계서",
        "화면설계서",
        "DB설계서",
    ]
    assert all(d["done"] is False for d in design["deliverables"])
    # 대괄호로 적은 산출물은 그것만 씁니다.
    assert [d["name"] for d in project["milestones"][1]["deliverables"]] == [
        "단위시험결과서"
    ]

    # 시간축에서의 위치. 1년짜리 프로젝트의 3월 말이면 4분의 1쯤입니다.
    assert 22 < design["percent"] < 26
    assert 0 <= project["timeline"]["percent"] <= 100


def test_산출물을_내면_마일스톤이_완료로_바뀐다():
    project = dev_projects.register_project(
        "E-DONE",
        "완료 확인용",
        stage="분석",
        start_date="2026-01-01",
        rts_date="2026-12-31",
        milestones="분석완료 2026-03-31 [요구사항정의서]",
    )
    assert project["milestones"][0]["done"] is False

    dev_projects.fill_form(
        {"project_name": "완료 확인용", "author": "김로아"},
        form_key="requirements",
        project_id=project["id"],
        user_id="E-DONE",
    )

    after = dev_projects.list_my_projects("E-DONE")["projects"][0]
    milestone = after["milestones"][0]
    assert milestone["done"] is True and milestone["done_count"] == 1


def test_마일스톤은_나중에_통째로_다시_적을_수_있다():
    project = dev_projects.register_project("E-MS", "마일스톤 교체", stage="기획")
    result = dev_projects.set_milestones(project["id"], "PP 2026-05-20, RTS 2026-06-30")

    assert result["ok"] is True
    assert [m["name"] for m in result["project"]["milestones"]] == ["PP", "RTS"]
    # 날짜가 없으면 시간축에 찍을 수 없으므로 거절합니다.
    assert dev_projects.set_milestones(project["id"], "이름만 있음")["ok"] is False


def test_양식을_채우면_초안이_남는다():
    project = dev_projects.register_project("E-DRAFT", "초안 과제", stage="분석")
    result = dev_projects.fill_form(
        {"project_name": "초안 과제", "author": "김로아"},
        form_key="requirements",
        project_id=project["id"],
        user_id="E-DRAFT",
    )

    assert result["ok"] and "초안 과제" in result["document"]
    # 양식 맨 위 설명(--- ---)은 결과물에 들어가면 안 됩니다.
    assert not result["document"].startswith("---")
    checklist = dev_projects.project_checklist(project["id"])
    assert "요구사항정의서" in checklist["done"]


def test_없는_양식은_쓸_수_있는_양식을_알려준다():
    result = dev_projects.fill_form({}, form_key="없는양식")
    assert result["ok"] is False and result["available"]


# ── 업적 정리 ───────────────────────────────────────────────────────────
def test_기간_밖의_업적은_빠진다():
    achievements.add_achievement("E-ACH", "작년 일", date="2025-05-01")
    achievements.add_achievement("E-ACH", "올해 일", date="2026-05-01", impact="30% 단축")

    found = achievements.list_achievements("E-ACH", "2026-01-01", "2026-12-31")

    assert [a["title"] for a in found["achievements"]] == ["올해 일"]


def test_다른_앱_기록을_업적으로_받아_정리한다():
    achievements.import_achievements(
        "E-IMP",
        [{"name": "품질 TF", "completed_on": "2026-03-02", "category": "협업"}],
        source="할 일 앱",
    )
    summary = achievements.summarize_period("E-IMP", "2026-01-01", "2026-12-31", "김로아")

    assert "품질 TF" in summary and "협업" in summary


# ── 주간보고 ────────────────────────────────────────────────────────────
def test_지난주_계획이_이번주_실적_초안이_된다():
    weekly.draft_weekly_report("E-WK", "김로아", "플랫폼", ["설계"], ["시험 계획"], week_of="2026-09-16")
    carried = weekly.carry_over_plan("E-WK", "2026-09-23")

    assert carried["found"] and carried["suggested_done_this_week"] == ["시험 계획"]


def test_이번주가_아닌_기록은_주간보고에_안_들어간다():
    collected = weekly.collect_records(
        "E-WK",
        [{"title": "이번 주 일", "date": "2026-09-17"}, {"title": "지난달 일", "date": "2026-08-01"}],
        week_of="2026-09-16",
    )
    assert collected["done_this_week"] == ["이번 주 일"]


# ── 회의 조율 ───────────────────────────────────────────────────────────
def test_가능한_사람이_많은_시간이_맨_앞에_온다():
    poll = meeting.create_poll("김로아", "리뷰", ["이하늘", "최바다"], ["10:00", "14:00"])
    meeting.submit_availability(poll["poll_id"], "이하늘", ["14:00"])
    meeting.submit_availability(poll["poll_id"], "최바다", ["14:00"])

    ranked = meeting.best_slots(poll["poll_id"])

    assert ranked["ranked_slots"][0]["slot"] == "14:00"
    assert ranked["all_available"] == ["14:00"]


def test_회신_안_한_사람만_리마인드_대상이_된다():
    poll = meeting.create_poll("김로아", "리뷰", ["이하늘", "최바다"], ["10:00"])
    meeting.submit_availability(poll["poll_id"], "이하늘", ["10:00"])

    assert meeting.draft_reminder(poll["poll_id"])["pending"] == ["최바다"]


def test_어렵다고_답한_시간으로_확정하면_경고한다():
    poll = meeting.create_poll("김로아", "리뷰", ["이하늘"], ["10:00", "14:00"])
    meeting.submit_availability(poll["poll_id"], "이하늘", ["10:00"])

    confirmed = meeting.confirm_meeting(poll["poll_id"], "14:00")

    assert confirmed["conflicts"] == ["이하늘"]


# ── 결재 추적 ───────────────────────────────────────────────────────────
def test_오래_멈춘_결재를_찾아_준다():
    approvals.register_approval("E-AP", "장비 구매", "팀장 검토", submitted_on="2020-01-01")
    stalled = approvals.stalled_approvals("E-AP", days=3)

    assert stalled["stalled_count"] == 1


def test_단계를_옮기면_이동_기록이_남는다():
    record = approvals.register_approval("E-AP2", "출장 신청", "팀장 검토")
    approvals.update_approval_step(record["id"], "임원 결재", approver="정상무")

    history = approvals.approval_history(record["id"])["history"]

    assert [h["step"] for h in history] == ["팀장 검토", "임원 결재"]
