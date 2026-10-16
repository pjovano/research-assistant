from __future__ import annotations

from _extract.linegeometry import LineMeasures

MIN_COLUMN_LINE_CHARS = 20
MIN_COLUMN_LINES = 3
MIN_GUTTER_POINTS = 12.0
MAX_ABUTTING_GAP_POINTS = 0.5
STYLE_SIZE_TOLERANCE_POINTS = 0.5
_LEFT, _RIGHT = 0, 2


class LineColumns:
    def __init__(self, lines: list[list]) -> None:
        self._lines = lines
        self._measures = LineMeasures(lines)

    def all(self) -> list[list[list]]:
        return self._split(self._lines)

    def _split(self, lines: list[list]) -> list[list[list]]:
        gutter = self._gutter(lines)
        if gutter is None:
            return [lines]
        left = [line for line in lines if self._right(line) <= gutter]
        return self._split(left) + self._split([line for line in lines if self._right(line) > gutter])

    def _gutter(self, lines: list[list]) -> float | None:
        return self._spaced_gutter(lines) or _RowCells(lines, self._measures).edge()

    def _spaced_gutter(self, lines: list[list]) -> float | None:
        if len(lines) < 2 * MIN_COLUMN_LINES:
            return None
        edges = sorted((self._left(line), self._right(line)) for line in lines)
        return next((right for right, count in self._crossings(edges, lines) if count >= MIN_COLUMN_LINES), None)

    def _crossings(self, edges: list[tuple[float, float]], lines: list[list]):
        for _left, right in edges:
            if any(self._left(line) < right + MIN_GUTTER_POINTS and self._right(line) > right for line in lines):
                continue
            left = [line for line in lines if self._right(line) <= right]
            beyond = [line for line in lines if self._right(line) > right]
            yield right, min(len(self._measures.rows(left)), len(self._measures.rows(beyond)))

    def _left(self, line: list) -> float:
        return self._measures.bounds(line)[_LEFT]

    def _right(self, line: list) -> float:
        return self._measures.bounds(line)[_RIGHT]


class _RowCells:
    def __init__(self, lines: list[list], measures: LineMeasures) -> None:
        self._lines = lines
        self._measures = measures
        self._rows = measures.rows(lines)

    def edge(self) -> float | None:
        edges = [self._right(left) for left, right in self._pairs() if self._sets_cells(left, right)]
        return next((edge for edge in edges if not self._is_crossed(edge)), None)

    def _pairs(self) -> list[tuple[list, list]]:
        return [(left, right) for left in self._lines for right in self._lines if left is not right]

    def _sets_cells(self, left: list, right: list) -> bool:
        if self._abuts(left, right):
            return self._wraps_beneath(left, right)
        return self._stand_apart(left, right) and self._both_wrap(left, right)

    def _abuts(self, left: list, right: list) -> bool:
        gap = self._left(right) - self._right(left)
        return abs(gap) <= MAX_ABUTTING_GAP_POINTS and self._holds_a_cell(right) and self._set_one_row(left, right)

    def _stand_apart(self, left: list, right: list) -> bool:
        gap = self._left(right) - self._right(left)
        holds_cells = self._holds_a_cell(left) and self._holds_a_cell(right)
        return gap > MAX_ABUTTING_GAP_POINTS and holds_cells and self._set_one_row(left, right)

    def _holds_a_cell(self, line: list) -> bool:
        return self._measures.inked_count(line) >= MIN_COLUMN_LINE_CHARS

    def _set_one_row(self, left: list, right: list) -> bool:
        same_size = abs(self._measures.size(left) - self._measures.size(right)) <= STYLE_SIZE_TOLERANCE_POINTS
        return same_size and self._measures.share_baseline(left, right)

    def _wraps_beneath(self, left: list, right: list) -> bool:
        edge = self._left(right)
        return any(all(self._right(line) <= edge for line in row) for row in self._rows_below(left))

    def _both_wrap(self, left: list, right: list) -> bool:
        edge = self._left(right)
        next_row = next(iter(self._rows_below(left)), [])
        continues_left = any(self._right(line) <= edge for line in next_row)
        continues_right = any(abs(self._left(line) - edge) <= MAX_ABUTTING_GAP_POINTS for line in next_row)
        return continues_left and continues_right

    def _rows_below(self, line: list) -> list[list[list]]:
        baseline = self._measures.baseline(line)
        return [row for row in self._rows if self._measures.baseline(row[0]) > baseline
                and not self._measures.share_baseline(row[0], line)]

    def _is_crossed(self, edge: float) -> bool:
        return any(self._left(line) < edge - MAX_ABUTTING_GAP_POINTS and self._right(line) > edge + MAX_ABUTTING_GAP_POINTS
                   for line in self._lines)

    def _left(self, line: list) -> float:
        return self._measures.bounds(line)[_LEFT]

    def _right(self, line: list) -> float:
        return self._measures.bounds(line)[_RIGHT]
