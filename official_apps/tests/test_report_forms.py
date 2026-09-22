"""보고서 양식 제작 앱 테스트.

핵심은 세 가지입니다.
  1) 종류·분량을 고르면 그 조합에 맞는 항목이 나온다
  2) 네 가지 형식(워드·엑셀·PPT·HTML)이 실제 파일로 만들어진다
  3) LLM 이 없어도 빈 양식은 반드시 나온다 (회사 밖에서도 돌아가야 하니까)
"""
from pathlib import Path

from report_forms import builder, catalog
from report_forms import server as report_forms


def _sample_doc() -> dict:
    sections = [dict(s, body="") for s in catalog.sections_for("검토보고", "1장")]
    sections[0]["body"] = "도입이 타당하며 3분기 착수를 건의함."
    return {
        "title": "A설비 도입 타당성 검토",
        "report_type": "검토보고",
        "length": "1장",
        "header": [("작성자", "김로아"), ("소속", "플랫폼개발팀")],
        "sections": sections,
    }


# ── 고르기 ─────────────────────────────────────────────────────────────
def test_분량을_올리면_항목이_늘어난다():
    짧게 = catalog.sections_for("결과보고", "1장")
    보통 = catalog.sections_for("결과보고", "3장")
    자세히 = catalog.sections_for("결과보고", "상세")
    assert len(짧게) < len(보통) < len(자세히)
    # 한 장짜리 항목은 긴 보고서에도 그대로 들어 있어야 합니다.
    assert {s["key"] for s in 짧게} <= {s["key"] for s in 자세히}


def test_회의결과보고를_결과보고로_잘못_알아듣지_않는다():
    assert catalog.resolve_type("회의결과보고") == "회의결과보고"
    assert catalog.resolve_type("검토 보고서") == "검토보고"
    assert catalog.resolve_type("진도보고") == "현황보고"
    assert catalog.resolve_type("듣도보도못한보고") == ""


def test_지시_내용을_보고_종류를_추천한다():
    assert recommend("설비 정지 사고 원인 보고해") == "이슈보고"
    assert recommend("평택 협력사 방문 결과 정리해줘") == "출장보고"
    assert recommend("A설비 도입 타당성 검토해서 보고") == "검토보고"


def recommend(text: str) -> str:
    return report_forms.recommend_options(text)["report_type"]


# ── 파일 만들기 ────────────────────────────────────────────────────────
def test_네_가지_형식이_모두_만들어진다(tmp_path: Path):
    doc = _sample_doc()
    for file_format in ("docx", "xlsx", "pptx", "html"):
        made = builder.build(doc, file_format, tmp_path, f"t_{file_format}")
        assert "error" not in made
        assert made["path"].exists() and made["path"].stat().st_size > 0


def test_HTML_은_바깥에서_아무것도_받아오지_않는다():
    page = builder.build_html(_sample_doc())
    assert "http://" not in page and "https://" not in page
    assert "A설비 도입 타당성 검토" in page


def test_내용이_없는_항목은_작성_안내가_대신_들어간다():
    page = builder.build_html(_sample_doc())
    assert "작성 안내" in page
    assert "도입이 타당하며" in page  # 채운 항목은 안내 대신 내용이 나옵니다


# ── 앱 기능 ────────────────────────────────────────────────────────────
def test_초안을_끄면_LLM_없이도_양식이_나온다():
    result = report_forms.build_report(
        "검토보고", title="A설비 도입 검토", length="1장", output_format="word", user_id="E1001"
    )
    assert result["ok"] is True
    assert result["drafted_by"] == "none"
    assert result["download_url"].endswith(".docx")
    assert "검토 결론" in result["sections"]


def test_초안을_켰는데_LLM_이_없으면_빈_양식으로_대신_준다():
    result = report_forms.build_report(
        "이슈보고", length="1장", output_format="html", draft=True, context="라인 정지 발생"
    )
    assert result["ok"] is True
    assert result["drafted_by"] == "none"
    assert "draft_error" in result  # 왜 초안이 없는지 알려 줍니다


def test_모르는_종류나_형식은_고를_수_있는_것을_알려준다():
    assert report_forms.build_report("아무보고")["choices"]
    assert report_forms.build_report("검토보고", output_format="hwp")["choices"]


def test_항목을_채우고_다른_형식으로_다시_뽑는다():
    made = report_forms.build_report("출장보고", length="1장", output_format="html")
    filled = report_forms.fill_section(made["report_id"], "주요 내용", "협력사 설비 상태 양호함.")
    assert filled["ok"] is True

    again = report_forms.export_report(made["report_id"], "ppt")
    assert again["ok"] is True and again["download_url"].endswith(".pptx")

    saved = report_forms.get_report(made["report_id"])
    bodies = {s["title"]: s["body"] for s in saved["sections"]}
    assert bodies["주요 내용"] == "협력사 설비 상태 양호함."


def test_LLM_답을_항목별로_나눈다():
    sections = [dict(s, body="") for s in catalog.sections_for("검토보고", "1장")]
    answer = "## 검토 결론\n도입이 타당함.\n\n## 검토 배경\n원가 절감 지시에 따름."
    bodies = report_forms._split_draft(answer, sections)
    assert bodies["conclusion"] == "도입이 타당함."
    assert bodies["background"] == "원가 절감 지시에 따름."


def test_LLM_이_제목을_다르게_적어도_순서대로_채운다():
    sections = [dict(s, body="") for s in catalog.sections_for("검토보고", "1장")]
    answer = "## 1. 결론\n도입 타당.\n\n## 2. 왜 하는가\n원가 절감."
    bodies = report_forms._split_draft(answer, sections)
    assert bodies[sections[0]["key"]] == "도입 타당."
