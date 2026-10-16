from __future__ import annotations

import statistics
from dataclasses import dataclass

from _extract.layerlines import box_of, inked, source_lines
from _extract.linegeometry import LineMeasures

ALIGNED_EDGE_POINTS = 0.5
MIN_EDGE_LINES = 2
MIN_TABLE_ROWS = 3
MAX_CELL_STEP_SHARE = 1.5


@dataclass(frozen=True)
class _CellLine:
    chars: list
    column: int

    @property
    def baseline(self) -> float:
        return statistics.median(char.baseline for char in inked(self.chars))

    @property
    def size(self) -> float:
        return statistics.median(char.size for char in inked(self.chars))


class LayerTable:
    def __init__(self, chars: list, reading) -> None:
        sources = source_lines(chars)
        edges = _ColumnEdges([box_of(source) for source in sources]).all()
        self._lines = [_CellLine(source, _column_at(edges, box_of(source).left)) for source in sources]
        self._column_count = len(edges)
        self._reading = reading

    def sets_more_columns_than(self, cell_count: int) -> bool:
        return self._column_count > cell_count and len(self._rows()) >= MIN_TABLE_ROWS

    def html(self) -> str:
        return table_html([[self._cell(row, column) for column in range(self._column_count)] for row in self._rows()])

    def _rows(self) -> list[list[_CellLine]]:
        return _CellRows(self._lines).all()

    def _cell(self, row: list[_CellLine], column: int) -> str:
        lines = sorted((line for line in row if line.column == column), key=lambda line: line.baseline)
        return self._reading.html_of_rows([line.chars for line in lines])


class _ColumnEdges:
    def __init__(self, boxes: list) -> None:
        self._boxes = boxes

    def all(self) -> list[float]:
        groups = _aligned_groups(sorted(box.left for box in self._boxes))
        interior = [group[0] for group in groups[1:] if len(group) >= MIN_EDGE_LINES and not self._is_crossed(group[0])]
        return groups[0][:1] + interior if groups else []

    def _is_crossed(self, edge: float) -> bool:
        return any(box.left < edge - ALIGNED_EDGE_POINTS and box.right > edge + ALIGNED_EDGE_POINTS
                   for box in self._boxes)


def _aligned_groups(lefts: list[float]) -> list[list[float]]:
    groups: list[list[float]] = []
    for left in lefts:
        if groups and left - groups[-1][0] <= ALIGNED_EDGE_POINTS:
            groups[-1].append(left)
        else:
            groups.append([left])
    return groups


def _column_at(edges: list[float], left: float) -> int:
    return max((index for index, edge in enumerate(edges) if edge <= left + ALIGNED_EDGE_POINTS), default=0)


class _CellRows:
    def __init__(self, lines: list[_CellLine]) -> None:
        self._lines = lines
        self._pitch = _line_pitch(lines)

    def all(self) -> list[list[_CellLine]]:
        rows: list[list[_CellLine]] = []
        for baseline_lines in _baseline_groups(self._lines):
            if rows and not self._starts_a_row(baseline_lines, rows[-1]):
                rows[-1].extend(baseline_lines)
            else:
                rows.append(list(baseline_lines))
        return rows

    def _starts_a_row(self, baseline_lines: list[_CellLine], row: list[_CellLine]) -> bool:
        opening = {line.column for line in baseline_lines if self._opens_a_cell(line, row)}
        continuing = {line.column for line in baseline_lines} - opening
        reopening = opening & {line.column for line in row}
        return bool(opening) and (not continuing or bool(reopening))

    def _opens_a_cell(self, line: _CellLine, row: list[_CellLine]) -> bool:
        reach = MAX_CELL_STEP_SHARE * self._pitch
        return not any(other.column == line.column and 0 < line.baseline - other.baseline <= reach for other in row)


def _line_pitch(lines: list[_CellLine]) -> float:
    steps = [step for column_lines in _by_column(lines) for step in _baseline_steps(column_lines)]
    return statistics.median(steps) if steps else 0.0


def _by_column(lines: list[_CellLine]) -> list[list[_CellLine]]:
    columns: dict[int, list[_CellLine]] = {}
    for line in sorted(lines, key=lambda held: held.baseline):
        columns.setdefault(line.column, []).append(line)
    return list(columns.values())


def _baseline_steps(lines: list[_CellLine]) -> list[float]:
    return [lower.baseline - upper.baseline for upper, lower in zip(lines, lines[1:])]


def _baseline_groups(lines: list[_CellLine]) -> list[list[_CellLine]]:
    sources = [line.chars for line in lines]
    by_source = {id(line.chars): line for line in lines}
    return [[by_source[id(source)] for source in row] for row in LineMeasures(sources).rows(sources)]


def table_html(rows: list[list[str]]) -> str:
    return "<table>" + "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows) \
        + "</table>"
