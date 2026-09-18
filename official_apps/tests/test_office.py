"""양식 채우기 테스트. 엑셀·워드는 '서식은 그대로, 글자만' 이 핵심입니다."""
from pathlib import Path

import pytest

from common import office


def test_텍스트_양식을_채운다(tmp_path: Path):
    source = tmp_path / "form.md"
    source.write_text("작성자: {{author}}\n내용: {{body}}", encoding="utf-8")

    result = office.fill_file(source, tmp_path / "out.md", {"author": "김로아", "body": "설계 완료"})

    assert (tmp_path / "out.md").read_text(encoding="utf-8") == "작성자: 김로아\n내용: 설계 완료"
    assert result["missing"] == []


def test_못_채운_항목을_알려준다(tmp_path: Path):
    source = tmp_path / "form.md"
    source.write_text("작성자: {{author}}\n기한: {{due}}", encoding="utf-8")

    result = office.fill_file(source, tmp_path / "out.md", {"author": "김로아"})

    assert result["missing"] == ["due"]
    assert result["filled"] == ["author"]
    assert "(미작성: due)" in (tmp_path / "out.md").read_text(encoding="utf-8")


def test_엑셀은_수식을_건드리지_않는다(tmp_path: Path):
    openpyxl = pytest.importorskip("openpyxl")
    source = tmp_path / "form.xlsx"
    book = openpyxl.Workbook()
    sheet = book.active
    sheet["A1"] = "{{title}}"
    sheet["A2"] = 10
    sheet["A3"] = 20
    sheet["A4"] = "=SUM(A2:A3)"  # 수식은 그대로 남아야 합니다
    book.save(source)

    office.fill_file(source, tmp_path / "out.xlsx", {"title": "9월 실적"})

    filled = openpyxl.load_workbook(tmp_path / "out.xlsx").active
    assert filled["A1"].value == "9월 실적"
    assert filled["A4"].value == "=SUM(A2:A3)"


def test_워드는_조각난_문장도_찾아_바꾼다(tmp_path: Path):
    docx = pytest.importorskip("docx")
    source = tmp_path / "form.docx"
    document = docx.Document()
    paragraph = document.add_paragraph()
    # 워드가 한 문장을 여러 조각으로 쪼개 저장한 상황을 그대로 흉내냅니다.
    for piece in ("작성자: {{", "author", "}}"):
        paragraph.add_run(piece)
    document.save(source)

    office.fill_file(source, tmp_path / "out.docx", {"author": "김로아"})

    assert docx.Document(str(tmp_path / "out.docx")).paragraphs[0].text == "작성자: 김로아"


def test_모르는_형식은_이유를_말한다(tmp_path: Path):
    source = tmp_path / "form.hwp"
    source.write_bytes(b"binary")

    with pytest.raises(ValueError, match="자동 채우기"):
        office.fill_file(source, tmp_path / "out.hwp", {})


def test_양식_안의_항목_이름을_모아_준다(tmp_path: Path):
    source = tmp_path / "form.md"
    source.write_text("{{author}} / {{ due }} / {{author}}", encoding="utf-8")

    assert office.find_fields(source) == ["author", "due"]
