from __future__ import annotations

from .chunking import (
    FILE_PAGE_FIRST_KEY,
    FILE_PAGE_LAST_KEY,
    FOLIO_FIRST_KEY,
    FOLIO_LAST_KEY,
    HEADING_PATH_KEY,
    TIME_FIRST_KEY,
    TIME_LAST_KEY,
)
from .fulltext import BASENAME, METADATA, PARENT_ID, TEXT, FullTextStore

_PARENT_FIELDS = (HEADING_PATH_KEY, FOLIO_FIRST_KEY, FOLIO_LAST_KEY, FILE_PAGE_FIRST_KEY, FILE_PAGE_LAST_KEY,
                  TIME_FIRST_KEY, TIME_LAST_KEY)
_NOT_FOUND = -1


class _MatchedSpan:
    def __init__(self, parent_text: str, child_text: str) -> None:
        self._child_text = child_text
        self._start = parent_text.find(child_text)

    def fields(self) -> dict:
        if self._start == _NOT_FOUND:
            return {"matched": self._child_text}
        return {"matched_start": self._start, "matched_end": self._start + len(self._child_text)}


class ResultAssembly:
    def __init__(self, fulltext: FullTextStore, result_limit: int) -> None:
        self._fulltext = fulltext
        self._result_limit = result_limit

    def entries(self, scored: list[tuple[str, float]]) -> list[dict]:
        best = self._best_child_per_parent(scored)
        parents = {parent[PARENT_ID]: parent for parent in self._fulltext.parents(list(best))}
        return [self._entry(parents[parent_id], child, score)
                for parent_id, (child, score) in best.items() if parent_id in parents]

    def _best_child_per_parent(self, scored: list[tuple[str, float]]) -> dict[str, tuple[dict, float]]:
        children = self._fulltext.children_by_id([chunk_id for chunk_id, _ in scored])
        best: dict[str, tuple[dict, float]] = {}
        for chunk_id, score in scored:
            room_left = len(best) < self._result_limit
            if chunk_id in children and room_left:
                best.setdefault(children[chunk_id][PARENT_ID], (children[chunk_id], score))
        return best

    @staticmethod
    def _entry(parent: dict, child: dict, score: float) -> dict:
        metadata = parent[METADATA]
        located = {field: metadata.get(field) for field in _PARENT_FIELDS}
        return {PARENT_ID: parent[PARENT_ID], BASENAME: parent[BASENAME], **located,
                TEXT: parent[TEXT], **_MatchedSpan(parent[TEXT], child[TEXT]).fields(), "score": score,
                "citekey": metadata.get("citekey", ""), "title": metadata.get("title", "")}
