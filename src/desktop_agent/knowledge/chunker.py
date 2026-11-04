from __future__ import annotations

import math
import re
from collections.abc import Sequence

from desktop_agent.knowledge.models import ChunkDraft, ParsedSection

SEPARATORS = ("\n\n", "\n", "。", "！", "？", "；", ". ", "! ", "? ", "; ", "，", ", ", " ", "")
_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")

Block = tuple[str, int, int]


def estimate_tokens(text: str) -> int:
    cjk = len(_CJK.findall(text))
    other = max(0, len(text) - cjk)
    return max(1, cjk + math.ceil(other / 4))


class RecursiveCharacterChunker:
    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        separators: Sequence[str] = SEPARATORS,
    ):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if not 0 <= chunk_overlap < chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = tuple(separators)

    def split(self, text: str) -> list[Block]:
        if not text:
            return []
        blocks = self._split_blocks(text, 0, self.separators)
        merged = self._merge_blocks(blocks)
        result: list[Block] = []
        previous = ""
        for group in merged:
            core = "".join(block[0] for block in group)
            start = group[0][1]
            end = group[-1][2]
            if previous and self.chunk_overlap:
                value = previous[-self.chunk_overlap :] + core
                start = max(0, end - len(value))
            else:
                value = core
            result.append((value, start, end))
            previous = core
        return result

    def split_sections(
        self, title: str, sections: Sequence[ParsedSection]
    ) -> list[ChunkDraft]:
        drafts: list[ChunkDraft] = []
        ordinal = 0
        for section in sections:
            for text, start, end in self.split(section.text):
                cleaned = text.strip()
                if not cleaned:
                    continue
                prefix = (
                    f"{title} / {section.heading_path}" if section.heading_path else title
                )
                drafts.append(
                    ChunkDraft(
                        ordinal=ordinal,
                        text=cleaned,
                        embed_text=f"{prefix}\n{cleaned}" if prefix else cleaned,
                        heading_path=section.heading_path,
                        page=section.page,
                        char_start=start,
                        char_end=end,
                        token_count=estimate_tokens(cleaned),
                    )
                )
                ordinal += 1
        return drafts

    def _split_blocks(self, text: str, start: int, separators: Sequence[str]) -> list[Block]:
        if len(text) <= self.chunk_size:
            return [(text, start, start + len(text))]
        if not separators:
            return [
                (text[index : index + self.chunk_size], start + index, start + min(index + self.chunk_size, len(text)))
                for index in range(0, len(text), self.chunk_size)
            ]
        separator = separators[0]
        if not separator:
            return [
                (text[index : index + self.chunk_size], start + index, start + min(index + self.chunk_size, len(text)))
                for index in range(0, len(text), self.chunk_size)
            ]
        parts = text.split(separator)
        blocks: list[Block] = []
        cursor = start
        for index, part in enumerate(parts):
            piece = part + (separator if index < len(parts) - 1 else "")
            piece_start = cursor
            cursor += len(piece)
            if not piece:
                continue
            if len(piece) <= self.chunk_size:
                blocks.append((piece, piece_start, piece_start + len(piece)))
            else:
                blocks.extend(self._split_blocks(piece, piece_start, separators[1:]))
        return blocks

    def _merge_blocks(self, blocks: Sequence[Block]) -> list[list[Block]]:
        merged: list[list[Block]] = []
        current: list[Block] = []
        length = 0
        for block in blocks:
            if current and length + len(block[0]) > self.chunk_size:
                merged.append(current)
                current = []
                length = 0
            current.append(block)
            length += len(block[0])
        if current:
            merged.append(current)
        return merged
