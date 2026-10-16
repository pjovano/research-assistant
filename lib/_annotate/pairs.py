from __future__ import annotations

from dataclasses import dataclass

from .markers import PageGrids
from .overlap import CoveredWords
from .resolver import PageWorkspace
from .spans import WordGrid


@dataclass(frozen=True)
class HighlightEdges:
    page: int
    index: int
    note: str
    begins_at_top: bool
    ends_at_bottom: bool

    @property
    def reference(self) -> str:
        return f"{self.page}:{self.index}"


class PairRule:
    @staticmethod
    def joins(earlier: HighlightEdges, later: HighlightEdges) -> bool:
        adjacent = later.page == earlier.page + 1
        shared_note = bool(earlier.note.strip()) and earlier.note == later.note
        return adjacent and shared_note and earlier.ends_at_bottom and later.begins_at_top


class PageEdges:
    def __init__(self, page, page_number: int, grid: WordGrid) -> None:
        self._page_number = page_number
        self._workspace = PageWorkspace(page, grid)
        self._covered = CoveredWords(self._workspace.grid)

    def of_all(self) -> list[HighlightEdges]:
        annotations = self._workspace.page.annots() or []
        return [self._edges(index, annotation) for index, annotation in enumerate(annotations)]

    def _edges(self, index: int, annotation) -> HighlightEdges:
        indices = self._covered.of(annotation) if PageWorkspace.is_highlight(annotation) else set()
        return HighlightEdges(self._page_number, index, annotation.info.get("content", ""),
                              self._begins_at_top(indices), self._ends_at_bottom(indices))

    def _begins_at_top(self, indices: set[int]) -> bool:
        first = self._workspace.body.first_line()
        return bool(indices) and first is not None and min(indices) <= first.last_index

    def _ends_at_bottom(self, indices: set[int]) -> bool:
        last = self._workspace.body.last_line()
        return bool(indices) and last is not None and max(indices) >= last.first_index


class HighlightPairs:
    def __init__(self, document, grids: PageGrids) -> None:
        self._grids = grids
        self._partners: dict[str, str] = {}
        self._found(document)

    def partner_of(self, reference: str) -> str | None:
        return self._partners.get(reference)

    def _found(self, document) -> None:
        previous: list[HighlightEdges] = []
        for number in range(document.page_count):
            current = self._edges(document[number], number + 1)
            self._join(previous, current)
            previous = current

    def _edges(self, page, page_number: int) -> list[HighlightEdges]:
        if page.first_annot is None:
            return []
        return PageEdges(page, page_number, self._grids.of(page_number)).of_all()

    def _join(self, earlier_edges: list[HighlightEdges], later_edges: list[HighlightEdges]) -> None:
        for earlier in earlier_edges:
            if earlier.reference in self._partners:
                continue
            later = self._match(earlier, later_edges)
            if later is not None:
                self._partners[earlier.reference] = later.reference
                self._partners[later.reference] = earlier.reference

    def _match(self, earlier: HighlightEdges, later_edges: list[HighlightEdges]) -> HighlightEdges | None:
        free = (later for later in later_edges if later.reference not in self._partners)
        return next((later for later in free if PairRule.joins(earlier, later)), None)
