from __future__ import annotations

import re
from dataclasses import dataclass

import pymupdf

from .pages import ColumnEstimate, PageCharacters, PageLayout

SIGLUM = r"[A-Z]+"
DEBRIS_DIGIT_RUN = r"[0-9OoIl]{1,3}"
MARKER_OPENER = re.compile(rf"^(?:{SIGLUM}(?![A-Za-z])|[0-9])")
MARKER_MIDDLE = re.compile(rf"^{DEBRIS_DIGIT_RUN}/{SIGLUM}$")
MARKER_CLOSER = re.compile(rf"^{DEBRIS_DIGIT_RUN}\]$")


@dataclass(frozen=True)
class WordBox:
    index: int
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    block: int = 0
    line: int = 0

    @property
    def rect(self):
        return pymupdf.Rect(self.x0, self.y0, self.x1, self.y1)

    @property
    def centre_x(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def line_key(self) -> tuple[int, int]:
        return (self.block, self.line)


@dataclass(frozen=True)
class WordSpan:
    page: int
    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start

    @property
    def indices(self) -> set[int]:
        return set(range(self.start, self.end))


class MarkerTail:
    @staticmethod
    def stripped(text: str) -> str:
        cut = text.rfind("[")
        if cut <= 0 or not MarkerTail._opens_marker(text[cut + 1:]):
            return text
        return text[:cut]

    @staticmethod
    def is_debris(text: str) -> bool:
        return MarkerTail.is_pure_debris(text) or MarkerTail._carries_opener(text)

    @staticmethod
    def is_pure_debris(text: str) -> bool:
        return (text.startswith("[") or
                bool(MARKER_MIDDLE.match(text)) or
                bool(MARKER_CLOSER.match(text)))

    @staticmethod
    def _carries_opener(text: str) -> bool:
        cut = text.find("[")
        return cut >= 0 and MarkerTail._opens_marker(text[cut + 1:])

    @staticmethod
    def _opens_marker(tail: str) -> bool:
        return bool(MARKER_OPENER.match(tail))


class WordGrid:
    def __init__(self, page) -> None:
        self._boxes = self._read(page)

    def __len__(self) -> int:
        return len(self._boxes)

    @property
    def boxes(self) -> list[WordBox]:
        return list(self._boxes)

    def box(self, index: int) -> WordBox:
        return self._boxes[index]

    def slice(self, start: int, end: int) -> list[WordBox]:
        return self._boxes[start:end]

    def text(self, start: int, end: int) -> str:
        return " ".join(box.text for box in self._boxes[start:end])

    def joined(self) -> str:
        return " ".join(box.text for box in self._boxes)

    def offsets(self) -> list[tuple[int, int, int]]:
        spans, position = [], 0
        for box in self._boxes:
            spans.append((position, position + len(box.text), box.index))
            position += len(box.text) + 1
        return spans

    def index_at(self, offset: int) -> int:
        for start, end, index in self.offsets():
            if start <= offset < end:
                return index
        return max(len(self._boxes) - 1, 0)

    def column(self):
        return ColumnEstimate(self._boxes).column()

    def _read(self, page) -> list[WordBox]:
        return [self._box(index, word) for index, word in enumerate(page.get_text("words"))]

    def _box(self, index: int, word: tuple) -> WordBox:
        x0, y0, x1, y1, text, block, line, _word_number = word
        return WordBox(index, x0, y0, x1, y1, text, block, line)


class SpanGeometry:
    def __init__(self, grid: WordGrid, characters: PageCharacters) -> None:
        self._grid = grid
        self._characters = characters

    def text(self, span: WordSpan) -> str:
        boxes = self._grid.slice(span.start, span.end)
        if not boxes:
            return ""
        words = [b.text for b in boxes[:-1]] + [MarkerTail.stripped(boxes[-1].text)]
        return " ".join(w for w in words if w)

    def quads(self, span: WordSpan) -> list:
        lines = self._lines(self._grid.slice(span.start, span.end))
        if not lines:
            return []
        rects = [self._line_rect(line) for line in lines]
        rects[-1] = self._trimmed_line_rect(lines[-1])
        return [rect.quad for rect in rects]

    def _lines(self, boxes: list[WordBox]) -> list[list[WordBox]]:
        grouped: list[list[WordBox]] = []
        for box in boxes:
            if grouped and grouped[-1][-1].line_key == box.line_key:
                grouped[-1].append(box)
            else:
                grouped.append([box])
        return grouped

    def _line_rect(self, line: list[WordBox]):
        rect = line[0].rect
        for box in line[1:]:
            rect |= box.rect
        return rect

    def _trimmed_line_rect(self, line: list[WordBox]):
        tail = self._trimmed_tail(line[-1])
        if len(line) == 1:
            return tail
        return self._line_rect(line[:-1]) | tail

    def _trimmed_tail(self, box: WordBox):
        keep = MarkerTail.stripped(box.text)
        if keep == box.text:
            return box.rect
        return self._characters.trimmed_rect(box.rect, len(keep))


class SpanNormalizer:
    def __init__(self, grid: WordGrid) -> None:
        self._grid = grid

    def normalized(self, span: WordSpan) -> WordSpan:
        return self.retracted(self.advanced(span))

    def advanced(self, span: WordSpan) -> WordSpan:
        return WordSpan(span.page, self._advanced_start(span), span.end)

    def retracted(self, span: WordSpan) -> WordSpan:
        return WordSpan(span.page, span.start, self._retracted_end(span))

    def _advanced_start(self, span: WordSpan) -> int:
        start = span.start
        while start < span.end and MarkerTail.is_debris(self._grid.box(start).text):
            start += 1
        return start

    def _retracted_end(self, span: WordSpan) -> int:
        end = span.end
        while end > span.start and MarkerTail.is_pure_debris(self._grid.box(end - 1).text):
            end -= 1
        return max(end, span.start)


class SpanValidator:
    def __init__(self, grid: WordGrid, layout: PageLayout) -> None:
        self._grid = grid
        self._layout = layout

    def errors(self, span: WordSpan) -> list[str]:
        return (self._range_errors(span) or
                self._side_errors(span))

    def _range_errors(self, span: WordSpan) -> list[str]:
        if span.length <= 0:
            return [f"empty span [{span.start}:{span.end}]"]
        if span.start < 0 or span.end > len(self._grid):
            return [f"span [{span.start}:{span.end}] outside page of {len(self._grid)} words"]
        return []

    def _side_errors(self, span: WordSpan) -> list[str]:
        sides = {self._layout.side_of(b.centre_x) for b in self._grid.slice(span.start, span.end)}
        if len(sides) > 1:
            return [f"span [{span.start}:{span.end}] crosses the gutter of a two-up spread"]
        return []
