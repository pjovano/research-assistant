from __future__ import annotations

import dataclasses
import functools
import html
import re
import statistics

from _extract.blocks import Block
from _extract.box import Box
from _extract.layercolumns import (
    MIN_COLUMN_LINE_CHARS,
    STYLE_SIZE_TOLERANCE_POINTS,
    LineColumns,
)
from _extract.linegeometry import SAME_BASELINE_SHARE, LineMeasures, baseline_of, bounds_of, inked, share_a_baseline, size_of

WHOLE_PAGE = Box(0.0, 0.0, 100000.0, 100000.0)
MIN_MARGIN_GAP_POINTS = 4.0
MIN_DROP_CAPITAL_ROWS = 2
MIN_DROP_CAPITAL_SIZE_SHARE = 1.5
RAISED_SIZE_SHARE = 0.85
MIN_COUNTED_LINES = 3
HELD_HEIGHT_TIE_SHARE = 0.25
HYPHEN = "-"
MARGINAL_REFERENCE_RE = re.compile(r"^(?:\d{1,4}[a-z]?|[a-z])$")


class PageLines:
    def __init__(self, layer, file_page: int, blocks: list[Block]) -> None:
        sources = _SourceLines(layer.chars_in(file_page, WHOLE_PAGE)).all()
        self._margin = _MarginalReferences(sources)
        self._sources = self._margin.without()
        self._owned = _Ownership(blocks).of(self._sources)
        self._references = self._margin.references()

    def of(self, block: Block) -> list[list]:
        return [list(row) for row in self._rows.get(block.identifier, [])]

    @functools.cached_property
    def _rows(self) -> dict[str, list[list]]:
        rows = {identifier: _Rows(sources).all() for identifier, sources in self._owned.items()}
        return _ReferencedRows(rows).with_references(self._references)

    def opening_top(self, block: Block) -> float:
        opening_lines = self.columns_of(block)[0] or self._covered_by(block)
        if not opening_lines:
            return block.bbox.top
        return min(_box_of(source)[1] for source in opening_lines)

    def _covered_by(self, block: Block) -> list[list]:
        return [source for source in self._sources if block.bbox.contains(box_of(source).center)]

    def columns_of(self, block: Block) -> list[list[list]]:
        return LineColumns(self._owned.get(block.identifier, [])).all()

    def lies_beside_the_column(self, block: Block) -> bool:
        sources = self._owned.get(block.identifier, [])
        return bool(sources) and all(self._margin.sets_beside_the_column(source) for source in sources)


def rows_of(chars: list) -> list[list]:
    return _Rows(_SourceLines(chars).all()).all()


def row_text(row: list) -> str:
    pieces = [char.char if index == 0 or char.line == row[index - 1].line else f" {char.char}"
              for index, char in enumerate(row)]
    return " ".join("".join(pieces).split())


def source_lines(chars: list) -> list[list]:
    return _SourceLines(chars).all()


def left_of(row: list) -> float:
    return _box_of([char for char in row if not char.in_margin] or row)[0]


def box_of(line: list) -> Box:
    return Box(*_box_of(line))


def box_of_rows(rows: list[list]) -> Box:
    return Box.union([box_of(row) for row in rows])


def paragraph_of_rows(rows: list[list]) -> str:
    text = html.escape(" ".join(row_text(row) for row in rows), quote=False)
    return f"<p>{text}</p>"


class _MarginalReferences:
    def __init__(self, sources: list[list]) -> None:
        self._sources = sources
        self._column = [source for source in sources if len(inked(source)) >= MIN_COLUMN_LINE_CHARS]
        self._marks = [source for source in sources if self._column and self._is_marginal_mark(source)]

    def without(self) -> list[list]:
        held = {id(mark) for mark in self._marks}
        return [source for source in self._sources if id(source) not in held]

    def references(self) -> list[list]:
        if _counts_lines_from_one(self._marks):
            return []
        return [[dataclasses.replace(char, in_margin=True) for char in inked(mark)] for mark in self._marks]

    def sets_beside_the_column(self, source: list) -> bool:
        is_short = len(inked(source)) < MIN_COLUMN_LINE_CHARS
        return bool(self._column) and is_short and self._lies_beside_column(source)

    def _is_marginal_mark(self, source: list) -> bool:
        return _is_reference_mark(source) and self._lies_beside_column(source) and self._is_set_apart(source)

    def _lies_beside_column(self, source: list) -> bool:
        box = _box_of(source)
        column_left = min(_box_of(line)[0] for line in self._column)
        column_right = max(_box_of(line)[2] for line in self._column)
        return box[2] + MIN_MARGIN_GAP_POINTS <= column_left or box[0] - MIN_MARGIN_GAP_POINTS >= column_right

    def _is_set_apart(self, source: list) -> bool:
        column_size = statistics.median(_size_of(line) for line in self._column)
        column_bold = statistics.mode(_is_bold(line) for line in self._column)
        resized = abs(_size_of(source) - column_size) > STYLE_SIZE_TOLERANCE_POINTS
        return resized or _is_bold(source) != column_bold


def _counts_lines_from_one(marks: list[list]) -> bool:
    texts = ["".join(char.char for char in inked(mark)) for mark in sorted(marks, key=_baseline_of)]
    numerals = [int(text) for text in texts if text.isdigit()]
    return len(numerals) >= MIN_COUNTED_LINES and numerals == list(range(1, len(numerals) + 1))


class _ReferencedRows:
    def __init__(self, rows_by_block: dict[str, list[list]]) -> None:
        self._rows_by_block = rows_by_block

    def with_references(self, references: list[list]) -> dict[str, list[list]]:
        beside = self._references_beside_rows(references)
        return {identifier: [_referenced(rows, position, beside.get((identifier, position), []))
                             for position in range(len(rows))]
                for identifier, rows in self._rows_by_block.items()}

    def _references_beside_rows(self, references: list[list]) -> dict[tuple[str, int], list]:
        beside: dict[tuple[str, int], list] = {}
        for reference in sorted(references, key=lambda held: _box_of(held)[0]):
            place = self._place_of(reference)
            if place is not None:
                beside[place] = _spaced_apart(beside[place], reference) if place in beside else reference
        return beside

    def _place_of(self, reference: list) -> tuple[str, int] | None:
        places = [(identifier, position) for identifier, rows in self._rows_by_block.items()
                  for position, row in enumerate(rows) if share_a_baseline((row, reference))]
        return min(places, key=lambda place: _distance_across(self._rows_by_block[place[0]][place[1]], reference),
                   default=None)


def _referenced(rows: list[list], position: int, reference: list) -> list:
    row = rows[position]
    if not reference:
        return row
    if position > 0 and _ends_hyphenated(rows[position - 1]):
        broken_word_end = _first_word_end(row)
        return _spaced_apart(row[:broken_word_end], reference) + row[broken_word_end:]
    return _spaced_apart(reference, row)


def _spaced_apart(first: list, second: list) -> list:
    return first + [dataclasses.replace(first[-1], char=" ")] + second


def _ends_hyphenated(row: list) -> bool:
    return inked(row)[-1].char == HYPHEN


def _first_word_end(row: list) -> int:
    first_ink = min(index for index, char in enumerate(row) if not char.is_blank)
    return next((index for index in range(first_ink, len(row)) if row[index].is_blank), len(row))


def _distance_across(row: list, reference: list) -> float:
    row_box, reference_box = _box_of(row), _box_of(reference)
    return max(reference_box[0] - row_box[2], row_box[0] - reference_box[2], 0.0)


class _Ownership:
    def __init__(self, blocks: list[Block]) -> None:
        self._blocks = blocks

    def of(self, sources: list[list]) -> dict[str, list[list]]:
        owned: dict[str, list[list]] = {}
        for source in sources:
            owner = self._owner_of(source)
            if owner is not None:
                owned.setdefault(owner.identifier, []).append(source)
        return owned

    def _owner_of(self, source: list) -> Block | None:
        box = box_of(source)
        holding = [(index, block) for index, block in enumerate(self._blocks) if block.bbox.contains(box.center)]
        return self._most_specific(_SiblingShares(holding, box).fullest()) if holding else self._widest(box)

    @staticmethod
    def _most_specific(candidates: list[tuple[int, Block]]) -> Block:
        return max(candidates, key=lambda held: _specificity(held[1], held[0]))[1]

    def _widest(self, box: Box) -> Block | None:
        overlapping = [(index, block) for index, block in enumerate(self._blocks) if box.overlap(block.bbox) > 0]
        if not overlapping:
            return None
        return max(overlapping, key=lambda held: (box.overlap(held[1].bbox), *_specificity(held[1], held[0])))[1]


class _SiblingShares:
    def __init__(self, candidates: list[tuple[int, Block]], box: Box) -> None:
        self._candidates = candidates
        self._shares = {index: box.height_share_held_by(block.bbox) for index, block in candidates}

    def fullest(self) -> list[tuple[int, Block]]:
        return [held for held in self._candidates if not self._is_outheld(held)]

    def _is_outheld(self, held: tuple[int, Block]) -> bool:
        index, block = held
        return any(other.kind == block.kind and self._shares[other_index] - self._shares[index] > HELD_HEIGHT_TIE_SHARE
                   for other_index, other in self._candidates)


class _Rows:
    def __init__(self, sources: list[list]) -> None:
        self._sources = sources

    def all(self) -> list[list]:
        capitals = _DropCapitals(self._sources)
        rows = [row for column in LineColumns(capitals.body()).all()
                for row in [self._joined(grouped) for grouped in _RaisedLines(_Rows(column).grouped()).attached()]]
        return capitals.opening(rows)

    def grouped(self) -> list[list[list]]:
        return LineMeasures(self._sources).rows(self._sources)

    @staticmethod
    def _joined(row: list[list]) -> list:
        return [char for line in sorted(row, key=lambda line: _box_of(line)[0]) for char in line]


class _RaisedLines:
    def __init__(self, rows: list[list[list]]) -> None:
        self._rows = rows

    def attached(self) -> list[list[list]]:
        attached: list[list[list]] = []
        for position, row in enumerate(self._rows):
            below = self._rows[position + 1] if position + 1 < len(self._rows) else None
            if below is not None and _is_raised_over(row, below):
                below[:0] = [[dataclasses.replace(char, raised=True) for char in line] for line in row]
            else:
                attached.append(row)
        return attached


def _is_raised_over(row: list[list], below: list[list]) -> bool:
    row_chars = [char for line in row for char in line]
    below_chars = [char for line in below for char in line]
    is_small = _size_of(row_chars) < RAISED_SIZE_SHARE * _size_of(below_chars)
    rise = _baseline_of(below_chars) - _baseline_of(row_chars)
    return is_small and 0 < rise < _size_of(below_chars)


class _DropCapitals:
    def __init__(self, sources: list[list]) -> None:
        self._sources = sources
        self._capitals = [source for source in sources if self._is_capital(source)]

    def body(self) -> list[list]:
        held = {id(capital) for capital in self._capitals}
        return [source for source in self._sources if id(source) not in held]

    def opening(self, rows: list[list]) -> list[list]:
        openings: dict[int, list] = {}
        for capital in self._capitals:
            openings.setdefault(self._row_opened(capital, rows), []).extend(capital)
        indented = {self._row_opened(capital, rows) for capital in self._capitals if _indents_beside(capital, rows)}
        return [openings.get(position, []) + (_unindented(row) if position in indented else row)
                for position, row in enumerate(rows)] or self._capitals

    def _is_capital(self, source: list) -> bool:
        if len(inked(source)) != 1:
            return False
        beside = self._dropped_beside(source)
        is_dropped = sets_a_drop_capital(_size_of(source), [_size_of(row) for row in beside])
        return is_dropped and _box_of(source)[0] <= min(_box_of(row)[0] for row in beside)

    def _dropped_beside(self, source: list) -> list[list]:
        top = _box_of(source)[1]
        return [other for other in self._sources
                if id(other) != id(source) and top <= _baseline_of(other) and _is_no_lower_than(other, source)]

    @staticmethod
    def _row_opened(capital: list, rows: list[list]) -> int:
        top = _box_of(capital)[1]
        opened = [position for position, row in enumerate(rows) if _baseline_of(row) >= top]
        return min(opened, default=len(rows) - 1)


def _indents_beside(capital: list, rows: list[list]) -> bool:
    top = _box_of(capital)[1]
    beside = [row for row in rows if top <= _baseline_of(row) and _is_no_lower_than(row, capital)]
    return len(beside) >= MIN_DROP_CAPITAL_ROWS and all(row[0].is_blank for row in beside)


def _unindented(row: list) -> list:
    first_ink = next(index for index, char in enumerate(row) if not char.is_blank)
    return row[first_ink:]


def _is_no_lower_than(line: list, capital: list) -> bool:
    return _baseline_of(line) <= _baseline_of(capital) + SAME_BASELINE_SHARE * _size_of(line)


def sets_a_drop_capital(size: float, sizes_beside: list[float]) -> bool:
    if len(sizes_beside) < MIN_DROP_CAPITAL_ROWS:
        return False
    return size >= MIN_DROP_CAPITAL_SIZE_SHARE * statistics.median(sizes_beside)


class _SourceLines:
    def __init__(self, chars: list) -> None:
        self._chars = chars

    def all(self) -> list[list]:
        by_number: dict[int, list] = {}
        for char in self._chars:
            by_number.setdefault(char.line, []).append(char)
        return [line for _number, line in sorted(by_number.items()) if any(not char.is_blank for char in line)]


def _is_reference_mark(line: list) -> bool:
    return MARGINAL_REFERENCE_RE.match("".join(char.char for char in inked(line))) is not None


def _is_bold(line: list) -> bool:
    return all(char.bold for char in inked(line))


def _specificity(block: Block, index: int) -> tuple:
    return (block.is_furniture, -block.bbox.area, -index)


_baseline_of = baseline_of
_size_of = size_of
_box_of = bounds_of
