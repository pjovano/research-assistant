from __future__ import annotations

from collections import Counter

from _extract.headings import MIN_SHAPE_CHARS
from _extract.runningheads import REPEATED_PAGES, folioless_shape

EDGE_LINES = 3
SAMPLED_PAGES = 40
MOST_PAGES_SHARE = 0.5


def evenly(pages: list[int], count: int) -> list[int]:
    if count >= len(pages):
        return list(pages)
    if count <= 0:
        return []
    if count == 1:
        return [pages[len(pages) // 2]]
    step = (len(pages) - 1) / (count - 1)
    return [pages[round(index * step)] for index in range(count)]


class RecurringEdgeLines:
    def __init__(self, layer) -> None:
        sampled = evenly(list(range(1, layer.page_count() + 1)), SAMPLED_PAGES)
        texts = [[line.text for line in layer.lines(page) if line.text.strip()] for page in sampled]
        edged = [page for page in texts if has_edges(page)]
        self._top = _recurring([page[:EDGE_LINES] for page in edged], len(edged))
        self._bottom = _recurring([page[-EDGE_LINES:] for page in edged], len(edged))

    def stripped(self, texts: list[str]) -> list[str]:
        bottom_start = max(0, len(texts) - EDGE_LINES)
        return [text for index, text in enumerate(texts) if not self._is_furniture(text, index, bottom_start)]

    def _is_furniture(self, text: str, index: int, bottom_start: int) -> bool:
        shape = folioless_shape(text)
        at_top = index < EDGE_LINES and shape in self._top
        return at_top or (index >= bottom_start and shape in self._bottom)


def has_edges(texts: list[str]) -> bool:
    return len(texts) > 2 * EDGE_LINES


def _recurring(edges: list[list[str]], page_count: int) -> set[str]:
    printing = Counter(shape for edge in edges for shape in {folioless_shape(text) for text in edge})
    return {shape for shape, pages in printing.items()
            if len(shape) >= MIN_SHAPE_CHARS and pages >= REPEATED_PAGES and pages > page_count * MOST_PAGES_SHARE}
