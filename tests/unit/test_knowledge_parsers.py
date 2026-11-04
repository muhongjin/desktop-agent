from __future__ import annotations

import pytest

from desktop_agent.knowledge.models import DocumentProcessingError
from desktop_agent.knowledge.parsers import parse_bytes


def test_markdown_headings_become_sections():
    content = "# 产品手册\n\n## 安装\n\n执行安装脚本。\n\n## 配置\n\n填写密钥。\n".encode()
    sections = parse_bytes("guide.md", content)
    assert [section.heading_path for section in sections] == [
        "产品手册 / 安装",
        "产品手册 / 配置",
    ]
    assert "执行安装脚本" in sections[0].text


def test_markdown_without_headings_is_single_section():
    sections = parse_bytes("notes.markdown", "只有正文".encode())
    assert len(sections) == 1
    assert sections[0].heading_path == ""


def test_plain_text_supports_gb18030():
    sections = parse_bytes("legacy.txt", "中文内容".encode("gb18030"))
    assert "中文内容" in sections[0].text


def test_unsupported_extension_is_rejected():
    with pytest.raises(DocumentProcessingError):
        parse_bytes("virus.exe", b"x")


def test_empty_text_file_is_rejected():
    with pytest.raises(DocumentProcessingError):
        parse_bytes("empty.txt", b"   ")


def test_docx_paragraphs_and_tables(tmp_path):
    docx = pytest.importorskip("docx")
    document = docx.Document()
    document.add_heading("第一章", level=1)
    document.add_paragraph("正文内容")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "字段"
    table.cell(0, 1).text = "说明"
    table.cell(1, 0).text = "name"
    table.cell(1, 1).text = "名称"
    path = tmp_path / "guide.docx"
    document.save(path)

    sections = parse_bytes("guide.docx", path.read_bytes())
    texts = "\n".join(section.text for section in sections)
    assert "正文内容" in texts
    assert "字段 | 说明" in texts


def test_xlsx_rows_use_sheet_name_as_heading(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "成员表"
    sheet.append(["姓名", "年龄"])
    sheet.append(["张三", "20"])
    path = tmp_path / "members.xlsx"
    workbook.save(path)

    sections = parse_bytes("members.xlsx", path.read_bytes())
    assert sections[0].heading_path == "成员表"
    assert "张三 | 20" in sections[0].text
