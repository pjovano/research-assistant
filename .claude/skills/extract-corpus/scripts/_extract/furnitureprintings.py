from __future__ import annotations

from collections import Counter

from _extract.blocks import PageBlocks
from _extract.runningheads import REPEATED_PAGES, folioless_shape


class FurniturePrintings:
    def __init__(self, pages: list[PageBlocks]) -> None:
        printed = [(page.file_page, {folioless_shape(text) for text in page.furniture_texts}) for page in pages]
        self._pages_printing = Counter(shape for _file_page, shapes in printed for shape in shapes)
        self._first_pages: dict[str, int] = {}
        for file_page, shapes in printed:
            for shape in shapes:
                self._first_pages.setdefault(shape, file_page)

    def pages_printing(self, shape: str) -> int:
        return self._pages_printing[shape]

    def first_page_printing(self, shape: str) -> int | None:
        return self._first_pages.get(shape)

    def repeated_shapes(self) -> frozenset[str]:
        return frozenset(shape for shape, pages in self._pages_printing.items() if pages >= REPEATED_PAGES)

    def repeats(self, text: str) -> bool:
        shape = folioless_shape(text)
        return bool(shape) and self.pages_printing(shape) >= REPEATED_PAGES

    def prints_once(self, text: str) -> bool:
        return bool(folioless_shape(text)) and not self.repeats(text)
