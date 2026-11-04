from __future__ import annotations

import re

import numpy as np

from desktop_agent.knowledge.repository import KnowledgeRepository

_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_WORD = re.compile(r"[A-Za-z0-9_]{3,}")


def build_fts_query(text: str, *, max_terms: int = 12) -> str:
    terms: list[str] = []
    seen: set[str] = set()
    for match in _WORD.finditer(text):
        term = match.group(0)
        key = term.lower()
        if key not in seen:
            seen.add(key)
            terms.append(term)
    cjk = "".join(_CJK.findall(text))
    for index in range(max(0, len(cjk) - 2)):
        term = cjk[index : index + 3]
        if term not in seen:
            seen.add(term)
            terms.append(term)
        if len(terms) >= max_terms:
            break
    return " OR ".join(f'"{term}"' for term in terms[:max_terms])


class DenseIndex:
    def __init__(self, repository: KnowledgeRepository):
        self.repository = repository
        self._cache: dict[str, tuple[int, list[str], np.ndarray]] = {}

    def invalidate(self, kb_id: str) -> None:
        self._cache.pop(kb_id, None)

    async def search(
        self, kb_id: str, version: int, vector: list[float], limit: int
    ) -> list[tuple[str, float]]:
        entry = self._cache.get(kb_id)
        if entry is None or entry[0] != version:
            ids, matrix = await self.repository.load_vectors(kb_id)
            entry = (version, ids, matrix)
            self._cache[kb_id] = entry
        _, ids, matrix = entry
        if matrix.size == 0 or limit <= 0:
            return []
        query = np.asarray(vector, dtype=np.float32)
        if query.ndim != 1 or query.size != matrix.shape[1]:
            return []
        norm = float(np.linalg.norm(query))
        if norm <= 0:
            return []
        scores = matrix @ (query / norm)
        order = np.argsort(-scores)[:limit]
        return [(ids[int(index)], float(scores[int(index)])) for index in order]


class SparseIndex:
    def __init__(self, repository: KnowledgeRepository):
        self.repository = repository

    async def search(self, kb_id: str, query: str, limit: int) -> list[str]:
        match = build_fts_query(query)
        if not match or limit <= 0:
            return []
        return await self.repository.search_fts(kb_id, match, limit)
