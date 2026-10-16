from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass

from _extract.box import Box
from _extract.failures import UsageFailure
from _extract.layer import LayerLine
from _extract.outline import PAGE_TOP

PAGE_BOTTOM = math.inf
END_POINT = "end"
_PAGE_POINT_RE = re.compile(r"^(?P<page>\d+)(?:\s*:\s*(?P<opening>\S.*))?$")
_SPACES_RE = re.compile(r"\s+")


class UnresolvedScopePoint(UsageFailure, ValueError):
    pass


@dataclass(frozen=True, order=True)
class PagePlace:
    file_page: int
    position: float = PAGE_TOP

    @classmethod
    def of_block(cls, block) -> PagePlace:
        return cls(block.file_page, block.bbox.center[1])


@dataclass(frozen=True)
class ScopeCut:
    position: float
    named_lines: tuple[Box, ...]

    def reaches(self, box: Box) -> bool:
        return all(line.shares_a_column_with(box) for line in self.named_lines)


@dataclass(frozen=True)
class ExcludedSpan:
    start: PagePlace
    resume: PagePlace
    start_line: Box | None = None
    resume_line: Box | None = None

    def holds(self, place: PagePlace) -> bool:
        return self.start <= place < self.resume

    def covers_page(self, file_page: int) -> bool:
        return self.holds(PagePlace(file_page)) and self.resume.file_page > file_page

    def overlap(self, file_page: int, top: float, bottom: float) -> tuple[float, float] | None:
        if not self.start.file_page <= file_page <= self.resume.file_page:
            return None
        opens = self.start.position if self.start.file_page == file_page else PAGE_TOP
        closes = self.resume.position if self.resume.file_page == file_page else PAGE_BOTTOM
        return _band_overlap((top, bottom), (opens, closes))

    def start_line_overlap(self, file_page: int, box: Box) -> tuple[float, float] | None:
        line = self.start_line
        if line is None or file_page != self.start.file_page or not line.shares_a_column_with(box):
            return None
        return _band_overlap((box.top, box.bottom), (line.top, line.bottom))

    def cuts(self, file_page: int) -> list[ScopeCut]:
        named_lines = self._named_lines_on(file_page)
        return [ScopeCut(place.position, named_lines) for place in (self.start, self.resume)
                if place.file_page == file_page and place.position != PAGE_TOP]

    def _named_lines_on(self, file_page: int) -> tuple[Box, ...]:
        named = ((self.start, self.start_line), (self.resume, self.resume_line))
        return tuple(line for place, line in named if line is not None and place.file_page == file_page)


def _band_overlap(band: tuple[float, float], other: tuple[float, float]) -> tuple[float, float] | None:
    opens, closes = max(band[0], other[0]), min(band[1], other[1])
    return (opens, closes) if opens < closes else None


class ExcludedSpans:
    def __init__(self, spans: list[ExcludedSpan]) -> None:
        self._spans = spans

    @classmethod
    def none(cls) -> ExcludedSpans:
        return cls([])

    def excludes(self, place: PagePlace) -> bool:
        return any(span.holds(place) for span in self._spans)

    def covers_page(self, file_page: int) -> bool:
        return any(span.covers_page(file_page) for span in self._spans)

    def resumed(self, place: PagePlace) -> PagePlace:
        return next((span.resume for span in self._spans
                     if span.holds(place) and span.resume.file_page == place.file_page), place)

    def cuts(self, file_page: int) -> list[ScopeCut]:
        return [cut for span in self._spans for cut in span.cuts(file_page)]

    def covered_height(self, file_page: int, box: Box) -> float:
        overlaps = [span.overlap(file_page, box.top, box.bottom) for span in self._spans]
        overlaps += [span.start_line_overlap(file_page, box) for span in self._spans]
        return _merged_height(sorted(overlap for overlap in overlaps if overlap is not None))


def _merged_height(overlaps: list[tuple[float, float]]) -> float:
    height, reached = 0.0, -math.inf
    for opens, closes in overlaps:
        height += max(0.0, closes - max(opens, reached))
        reached = max(reached, closes)
    return height


@dataclass(frozen=True)
class ScopePoint:
    text: str
    file_page: int | None
    opening: str | None

    @classmethod
    def parsed(cls, text: str) -> ScopePoint:
        stripped = text.strip()
        if stripped.casefold() == END_POINT:
            return cls(text, None, None)
        matched = _PAGE_POINT_RE.match(stripped)
        if matched is None:
            raise UnresolvedScopePoint(f"not a scope point: {text!r}; write 'end', '<file page>', "
                                       "or '<file page>: <opening words of one line>'")
        return cls(text, int(matched.group("page")), matched.group("opening"))

    @property
    def is_end(self) -> bool:
        return self.file_page is None


class ScopePoints:
    def __init__(self, layer) -> None:
        self._layer = layer

    def spans(self, pairs: list[tuple[str, str]]) -> ExcludedSpans:
        return ExcludedSpans([self._span(start, resume) for start, resume in pairs])

    def _span(self, start: str, resume: str) -> ExcludedSpan:
        start_point, resume_point = ScopePoint.parsed(start), ScopePoint.parsed(resume)
        span = ExcludedSpan(self._place(start_point), self._place(resume_point),
                            self._line_box(start_point), self._line_box(resume_point))
        if span.resume <= span.start:
            raise UnresolvedScopePoint(f"the span from {start!r} resumes at {resume!r}, which does not follow it")
        return span

    def _place(self, point: ScopePoint) -> PagePlace:
        if point.is_end:
            return PagePlace(self._layer.page_count() + 1)
        if not 1 <= point.file_page <= self._layer.page_count():
            raise UnresolvedScopePoint(f"{point.text!r} names file page {point.file_page}, outside the PDF")
        if point.opening is None:
            return PagePlace(point.file_page)
        return PagePlace(point.file_page, self._named_line(point).y0)

    def _line_box(self, point: ScopePoint) -> Box | None:
        if point.is_end or point.opening is None:
            return None
        return self._named_line(point).box

    def _named_line(self, point: ScopePoint) -> LayerLine:
        wanted = comparable(point.opening)
        lines = [(comparable(line.text), line) for line in self._layer.lines(point.file_page)]
        named = [line for text, line in lines if text == wanted]
        if named and _stacked_at_one_place(named):
            return named[0]
        return self._only_line_opened(point, [line for text, line in lines if text.startswith(wanted)])

    @staticmethod
    def _only_line_opened(point: ScopePoint, lines: list[LayerLine]) -> LayerLine:
        if not lines or not _stacked_at_one_place(lines):
            raise UnresolvedScopePoint(f"{point.text!r} opens {len(lines)} lines of file page {point.file_page} "
                                       "at different places; a point opens exactly one line, or the copies of one "
                                       "line the text layer stacks at one place: quote more of the line's words")
        return lines[0]


def _stacked_at_one_place(lines: list[LayerLine]) -> bool:
    first = lines[0].box
    return all(first.shares_a_region_with(line.box) for line in lines[1:])


def comparable(text: str) -> str:
    return _SPACES_RE.sub(" ", unicodedata.normalize("NFC", text)).strip().casefold()
