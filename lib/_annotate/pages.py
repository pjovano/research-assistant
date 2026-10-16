from __future__ import annotations

import re
import statistics
from dataclasses import dataclass

import pymupdf

from _pagetext.folio import FOLIO_WORD_PATTERN

SPREAD_ASPECT_RATIO = 1.15
LEFT = "left"
RIGHT = "right"
SINGLE = "single"

CONTAINMENT_RATIO = 0.5
LINE_OVERLAP_RATIO = 0.5
SMALL_LINE_RATIO = 0.85
WIDE_GAP_RATIO = 1.6
MIN_LINES_FOR_MARGINS = 3
FOLIO_WORD = re.compile(rf"^(?:{FOLIO_WORD_PATTERN})$")


class RectContainment:
    def holds(self, box, rect) -> bool:
        area = box.get_area()
        if area <= 0:
            return False
        return (box & rect).get_area() > CONTAINMENT_RATIO * area


class PageLayout:
    def __init__(self, page) -> None:
        self._page = page

    @property
    def is_spread(self) -> bool:
        rect = self._page.rect
        return rect.width > rect.height * SPREAD_ASPECT_RATIO

    @property
    def midline(self) -> float:
        return self._page.rect.width / 2

    def side_of(self, centre_x: float) -> str:
        if not self.is_spread:
            return SINGLE
        return LEFT if centre_x < self.midline else RIGHT


@dataclass(frozen=True)
class VisualLine:
    boxes: tuple

    @property
    def top(self) -> float:
        return min(box.y0 for box in self.boxes)

    @property
    def bottom(self) -> float:
        return max(box.y1 for box in self.boxes)

    @property
    def height(self) -> float:
        return self.bottom - self.top

    @property
    def first_index(self) -> int:
        return min(box.index for box in self.boxes)

    @property
    def last_index(self) -> int:
        return max(box.index for box in self.boxes)

    @property
    def carries_folio(self) -> bool:
        edges = (self.boxes[0].text, self.boxes[-1].text)
        return any(FOLIO_WORD.match(text.strip()) for text in edges)

    def overlaps(self, other: "VisualLine") -> bool:
        shared = min(self.bottom, other.bottom) - max(self.top, other.top)
        return shared >= LINE_OVERLAP_RATIO * min(self.height, other.height)

    def joined(self, other: "VisualLine") -> "VisualLine":
        return VisualLine(tuple(sorted(self.boxes + other.boxes, key=lambda box: box.x0)))


class PageLines:
    def __init__(self, boxes) -> None:
        self._lines = self._merged(self._by_text_line(boxes))

    def lines(self) -> list[VisualLine]:
        return list(self._lines)

    def _by_text_line(self, boxes) -> list[VisualLine]:
        grouped: dict = {}
        for box in boxes:
            grouped.setdefault(box.line_key, []).append(box)
        lines = [VisualLine(tuple(group)) for group in grouped.values()]
        return sorted(lines, key=lambda line: line.top)

    def _merged(self, lines: list[VisualLine]) -> list[VisualLine]:
        merged: list[VisualLine] = []
        for line in lines:
            if merged and merged[-1].overlaps(line):
                merged[-1] = merged[-1].joined(line)
            else:
                merged.append(line)
        return merged


class BodyLines:
    def __init__(self, lines: list[VisualLine]) -> None:
        self._lines = lines
        self._body = self._trimmed()

    def first(self) -> VisualLine | None:
        return self._body[0] if self._body else None

    def last(self) -> VisualLine | None:
        return self._body[-1] if self._body else None

    def _trimmed(self) -> list[VisualLine]:
        if len(self._lines) < MIN_LINES_FOR_MARGINS:
            return list(self._lines)
        start = self._first_body_position()
        end = self._end_of_body(start)
        return self._lines[start:end]

    def _first_body_position(self) -> int:
        start = 0
        while start < len(self._lines) - 1 and self._is_marginal(start, start + 1):
            start += 1
        return start

    def _end_of_body(self, start: int) -> int:
        end = len(self._lines)
        while end - 1 > start and self._is_marginal(end - 1, end - 2):
            end -= 1
        return end

    def _is_marginal(self, position: int, neighbour: int) -> bool:
        line = self._lines[position]
        return line.carries_folio or self._is_small(line) or self._is_detached(line, neighbour)

    def _is_small(self, line: VisualLine) -> bool:
        return line.height < SMALL_LINE_RATIO * self._modal_height()

    def _is_detached(self, line: VisualLine, neighbour: int) -> bool:
        gap = abs(self._lines[neighbour].top - line.top)
        return gap > WIDE_GAP_RATIO * self._modal_pitch()

    def _modal_height(self) -> int:
        return statistics.mode(round(line.height) for line in self._lines)

    def _modal_pitch(self) -> int:
        tops = [line.top for line in self._lines]
        return statistics.mode(round(later - earlier) for earlier, later in zip(tops, tops[1:]))


class PageBody:
    def __init__(self, boxes, layout: PageLayout) -> None:
        self._boxes = boxes
        self._layout = layout

    def first_line(self) -> VisualLine | None:
        return self._lines_on(LEFT).first()

    def last_line(self) -> VisualLine | None:
        return self._lines_on(RIGHT).last()

    def _lines_on(self, spread_side: str) -> BodyLines:
        wanted = [box for box in self._boxes if self._is_on(box, spread_side)]
        return BodyLines(PageLines(wanted).lines())

    def _is_on(self, box, spread_side: str) -> bool:
        return self._layout.side_of(box.centre_x) in (SINGLE, spread_side)


@dataclass(frozen=True)
class TextColumn:
    left: float
    right: float


class ColumnEstimate:
    def __init__(self, boxes) -> None:
        self._boxes = boxes

    def column(self) -> TextColumn | None:
        if not self._boxes:
            return None
        return TextColumn(self._modal_left(), self._modal_right())

    def _modal_left(self) -> int:
        return statistics.mode(round(box.x0) for box in self._boxes)

    def _modal_right(self) -> int:
        return statistics.mode(round(box.x1) for box in self._boxes)


class PageCharacters:
    def __init__(self, page) -> None:
        self._page = page
        self._chars: list | None = None

    def trimmed_rect(self, rect, keep_length: int):
        inside = [c for c in self._collected() if self._within(c, rect)]
        kept = inside[:keep_length]
        return self._union(kept) if kept else rect

    def _collected(self) -> list:
        if self._chars is None:
            self._chars = self._collect()
        return self._chars

    def _collect(self) -> list:
        collected: list = []
        for block in self._page.get_text("rawdict").get("blocks", []):
            for line in block.get("lines", []):
                collected.extend(self._chars_of(line))
        return collected

    def _chars_of(self, line) -> list:
        collected: list = []
        for span in line.get("spans", []):
            collected.extend(span.get("chars", []))
        return collected

    def _within(self, char, rect) -> bool:
        return RectContainment().holds(pymupdf.Rect(char["bbox"]), rect)

    def _union(self, chars):
        rect = pymupdf.Rect(chars[0]["bbox"])
        for char in chars[1:]:
            rect |= pymupdf.Rect(char["bbox"])
        return rect
