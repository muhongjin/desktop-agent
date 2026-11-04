from __future__ import annotations

import pytest

from desktop_agent.knowledge.chunker import RecursiveCharacterChunker, estimate_tokens
from desktop_agent.knowledge.models import ParsedSection


def test_short_text_returns_single_chunk():
    result = RecursiveCharacterChunker(512, 50).split("短文本")
    assert result == [("短文本", 0, 3)]


def test_long_text_respects_size_and_keeps_overlap():
    text = "第一段内容。" * 300
    pieces = RecursiveCharacterChunker(200, 40).split(text)
    assert len(pieces) > 1
    for value, start, end in pieces:
        assert 0 < len(value) <= 240
        assert 0 <= start <= end
    assert pieces[1][0][:40] == pieces[0][0][-40:]


def test_long_paragraph_is_hard_split():
    drafts = RecursiveCharacterChunker(50, 0).split_sections("d", [ParsedSection("a" * 200)])
    assert len(drafts) >= 4
    assert all(len(draft.text) <= 50 for draft in drafts)


def test_sections_keep_heading_page_and_embed_prefix():
    drafts = RecursiveCharacterChunker(100, 10).split_sections(
        "手册", [ParsedSection("安装步骤", heading_path="第一章", page=3)]
    )
    assert drafts[0].heading_path == "第一章"
    assert drafts[0].page == 3
    assert drafts[0].embed_text == "手册 / 第一章\n安装步骤"
    assert drafts[0].ordinal == 0


def test_blank_sections_are_skipped():
    drafts = RecursiveCharacterChunker(100, 10).split_sections(
        "手册", [ParsedSection("   ", heading_path="空"), ParsedSection("内容")]
    )
    assert [draft.text for draft in drafts] == ["内容"]


def test_estimate_tokens_counts_cjk_and_ascii():
    assert estimate_tokens("中文") == 2
    assert estimate_tokens("abcdefgh") == 2
    assert estimate_tokens("") == 1


def test_invalid_parameters_are_rejected():
    with pytest.raises(ValueError):
        RecursiveCharacterChunker(100, 100)
    with pytest.raises(ValueError):
        RecursiveCharacterChunker(0, 0)
