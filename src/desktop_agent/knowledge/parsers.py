from __future__ import annotations

import io
import re
from collections.abc import Sequence
from pathlib import Path

from desktop_agent.knowledge.models import DocumentProcessingError, ParsedSection

SUPPORTED_EXTENSIONS = frozenset({".txt", ".md", ".markdown", ".pdf", ".docx", ".xlsx"})
_MARKDOWN_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_DOCX_HEADING = re.compile(r"^(?:Heading|标题)\s*(\d+)$", re.IGNORECASE)


def supported_file(path: str | Path) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS


def parse_file(path: str | Path) -> list[ParsedSection]:
    file_path = Path(path)
    return parse_bytes(file_path.name, file_path.read_bytes())


def parse_bytes(filename: str, data: bytes) -> list[ParsedSection]:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise DocumentProcessingError(f"不支持的文件类型：{suffix or filename}")
    if suffix in {".txt"}:
        return _parse_plain(_decode(data))
    if suffix in {".md", ".markdown"}:
        return _parse_markdown(_decode(data))
    if suffix == ".pdf":
        return _parse_pdf(data)
    if suffix == ".docx":
        return _parse_docx(data)
    return _parse_xlsx(data)


def _decode(data: bytes) -> str:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace")
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _parse_plain(text: str) -> list[ParsedSection]:
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not cleaned:
        raise DocumentProcessingError("文件没有可提取的文本")
    return [ParsedSection(text=cleaned)]


def _parse_markdown(text: str) -> list[ParsedSection]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    sections: list[ParsedSection] = []
    stack: list[tuple[int, str]] = []
    buffer: list[str] = []

    def flush() -> None:
        body = "\n".join(buffer).strip()
        buffer.clear()
        if body:
            sections.append(
                ParsedSection(text=body, heading_path=" / ".join(title for _, title in stack))
            )

    for line in lines:
        match = _MARKDOWN_HEADING.match(line)
        if match is None:
            buffer.append(line)
            continue
        flush()
        level = len(match.group(1))
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, match.group(2).strip()))
    flush()
    if not sections:
        raise DocumentProcessingError("文件没有可提取的文本")
    return sections


def _parse_pdf(data: bytes) -> list[ParsedSection]:
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise DocumentProcessingError("缺少 pypdf，无法解析 PDF") from error
    try:
        reader = PdfReader(io.BytesIO(data))
        sections = []
        for index, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                sections.append(ParsedSection(text=text, page=index))
    except Exception as error:
        raise DocumentProcessingError(f"PDF 解析失败：{error}") from error
    if not sections:
        raise DocumentProcessingError("PDF 没有可提取的文本（可能是扫描件）")
    return sections


def _parse_docx(data: bytes) -> list[ParsedSection]:
    try:
        import docx
    except ImportError as error:
        raise DocumentProcessingError("缺少 python-docx，无法解析 Word 文档") from error
    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as error:
        raise DocumentProcessingError(f"Word 文档解析失败：{error}") from error
    sections: list[ParsedSection] = []
    stack: list[tuple[int, str]] = []
    buffer: list[str] = []

    def flush() -> None:
        body = "\n".join(buffer).strip()
        buffer.clear()
        if body:
            sections.append(
                ParsedSection(text=body, heading_path=" / ".join(title for _, title in stack))
            )

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        style_name = paragraph.style.name if paragraph.style is not None else ""
        match = _DOCX_HEADING.match(style_name) or _DOCX_HEADING.match(text)
        level = int(match.group(1)) if match else None
        if level is not None and style_name.lower().startswith(("heading", "标题")):
            flush()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, text))
            continue
        buffer.append(text)
    flush()
    for table in document.tables:
        rows = []
        for row in table.rows:
            cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
            if any(cells):
                rows.append(" | ".join(cells))
        if rows:
            sections.append(ParsedSection(text="\n".join(rows)))
    if not sections:
        raise DocumentProcessingError("Word 文档没有可提取的文本")
    return sections


def _parse_xlsx(data: bytes) -> list[ParsedSection]:
    try:
        import openpyxl
    except ImportError as error:
        raise DocumentProcessingError("缺少 openpyxl，无法解析 Excel 文件") from error
    try:
        workbook = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as error:
        raise DocumentProcessingError(f"Excel 解析失败：{error}") from error
    sections = []
    try:
        for sheet in workbook.worksheets:
            rows: list[str] = []
            for row in sheet.iter_rows(values_only=True):
                cells = [str(value).strip() for value in row if value is not None]
                if cells:
                    rows.append(" | ".join(cells))
            if rows:
                sections.append(ParsedSection(text="\n".join(rows), heading_path=sheet.title))
    finally:
        workbook.close()
    if not sections:
        raise DocumentProcessingError("Excel 没有可提取的内容")
    return sections


def merge_sections(sections: Sequence[ParsedSection]) -> str:
    return "\n\n".join(section.text for section in sections)
