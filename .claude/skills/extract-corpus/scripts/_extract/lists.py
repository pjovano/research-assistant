from __future__ import annotations

import re
import statistics
from dataclasses import dataclass

from _extract.box import Box
from _extract.capitallines import DropCapitalLines
from _extract.layer import LayerLine, TextLayer
from _extract.layercolumns import MIN_GUTTER_POINTS
from _extract.layerlines import MARGINAL_REFERENCE_RE, SAME_BASELINE_SHARE
from _extract.notenumbers import LAYER_LINE_OPENING_RE

MARGIN_TOLERANCE_POINTS = 2.5
COLUMN_GAP_POINTS = 60.0
MIN_COLUMN_LINES = 5
RIGHT_EDGE_TOLERANCE_POINTS = 3.0
HANGING_INDENT_SHARE = 0.25
MIN_FLUSH_RUN_ON_LINES = 3
FLUSH_RUN_ON_SHARE = 0.75
MIN_NUMBERED_ENTRIES = 2
BLANK_LINE_PITCHES = 2.0
MIN_RUN_IN_ENTRIES = 2
LABEL_WIDTH_SHARE = 0.5
FULL_STOP = "."

_HYPHEN_END_RE = re.compile(r"(\w)-$")
_CLOSING_PUNCTUATION_RE = re.compile(r"[.:;?!][)\]”’\"']*$")
_ENTRY_OPENING_RE = re.compile(
    r"^[^\W\d_](?:[\w'’-]*)(?:\s+[\w'’-]+)?,(?:\s+[^\W\d_]\.){1,3}\s*\(\s*\d{4}")


@dataclass(frozen=True)
class ListEntry:
    text: str
    bbox: Box


class HangingIndentList:
    def __init__(self, layer: TextLayer) -> None:
        self._layer = layer

    def entries(self, file_page: int, bbox: Box) -> list[str]:
        return [entry.text for entry in self.boxed_entries(file_page, [Box.of(bbox)])]

    def boxed_entries(self, file_page: int, boxes: list[Box]) -> list[ListEntry]:
        entries: list[ListEntry] = []
        measure = _PageMeasure(self._layer.lines(file_page))
        for column in self._columns(self._lines(file_page, boxes)):
            entries.extend(self._entries_of(column, measure.right_edge(column)))
        return entries

    def columns(self, file_page: int, boxes: list[Box]) -> list[list[LayerLine]]:
        return self._columns(self._lines(file_page, boxes))

    def is_numbered(self, file_page: int, boxes: list[Box]) -> bool:
        return bool(_Numbering().openings(self._lines(file_page, boxes)))

    def sets_a_label_column(self, file_page: int, boxes: list[Box]) -> bool:
        return _LabelList(self._lines(file_page, boxes)).labels_wrapped_entries()

    def runs_labels_into_entries(self, file_page: int, boxes: list[Box]) -> bool:
        return _RunInLabelList(self._lines(file_page, boxes)).labels_wrapped_entries()

    def _lines(self, file_page: int, boxes: list[Box]) -> list[LayerLine]:
        held = {line for box in boxes for line in self._layer.lines_in(file_page, box)}
        lines = [line for line in self._layer.lines_in(file_page, Box.union(boxes)) if line in held
                 and line.text.strip()]
        return _in_reading_order(_WordRuns(DropCapitalLines(lines).folded()).joined())

    def _columns(self, lines: list[LayerLine]) -> list[list[LayerLine]]:
        if len(lines) < 2 * MIN_COLUMN_LINES:
            return [lines]
        starts = sorted(line.x0 for line in lines)
        gaps = [(later - earlier, earlier) for earlier, later in zip(starts, starts[1:])]
        widest, boundary = max(gaps)
        if widest < COLUMN_GAP_POINTS:
            return [lines]
        left = [line for line in lines if line.x0 <= boundary]
        right = [line for line in lines if line.x0 > boundary]
        return [left, right] if _stand_as_columns(left, right) else [lines]

    def _entries_of(self, lines: list[LayerLine], right_edge: float) -> list[ListEntry]:
        if not lines:
            return []
        shape = _ListShape(lines, _Numbering().openings(lines), right_edge)
        groups: list[list[LayerLine]] = []
        for index, (previous, line) in enumerate(zip([None] + lines, lines)):
            if groups and shape.continues(index, previous, line):
                groups[-1].append(line)
            else:
                groups.append([line])
        return [self._entry(group) for group in groups]

    def _entry(self, group: list[LayerLine]) -> ListEntry:
        text = group[0].text.strip()
        for line in group[1:]:
            text = self._joined(text, line.text.strip())
        bottom = max(2 * line.center[1] - line.y0 for line in group)
        return ListEntry(text, Box(min(line.x0 for line in group), min(line.y0 for line in group),
                                   max(line.x1 for line in group), bottom))

    def _joined(self, entry: str, more: str) -> str:
        if _HYPHEN_END_RE.search(entry):
            return _HYPHEN_END_RE.sub(r"\1", entry) + more
        return f"{entry} {more}"


class _PageMeasure:
    def __init__(self, page_lines: list[LayerLine]) -> None:
        self._page_lines = page_lines

    def right_edge(self, column: list[LayerLine]) -> float:
        own_edge = max((line.x1 for line in column), default=0.0)
        margin = min((line.x0 for line in column), default=0.0)
        return max(own_edge, self._most_reached_edge(margin, own_edge))

    def _most_reached_edge(self, margin: float, own_edge: float) -> float:
        ends = [self._row_end(line, own_edge) for line in self._page_lines
                if abs(line.x0 - margin) <= MARGIN_TOLERANCE_POINTS]
        return max(ends, key=lambda end: sum(1 for other in ends if _ends_together(other, end)), default=0.0)

    def _row_end(self, line: LayerLine, own_edge: float) -> float:
        row = [other for other in self._page_lines
               if _shares_a_row(line, other) and line.x0 <= other.x0 <= own_edge]
        return max((other.x1 for other in row), default=line.x1)


class _WordRuns:
    def __init__(self, lines: list[LayerLine]) -> None:
        self._lines = lines

    def joined(self) -> list[LayerLine]:
        runs: dict[int, LayerLine] = {}
        for position in sorted(range(len(self._lines)), key=lambda position: self._lines[position].x0):
            line = self._lines[position]
            continued = next((start for start, run in runs.items() if self._runs_on_into(run, line)), None)
            if continued is None:
                runs[position] = line
            else:
                runs[continued] = self._joined(runs[continued], line)
        return [runs[position] for position in sorted(runs)]

    @staticmethod
    def _runs_on_into(run: LayerLine, line: LayerLine) -> bool:
        word_space = line.x0 - run.x1
        is_word_spaced = 0 <= word_space < MIN_GUTTER_POINTS
        return _shares_a_row(run, line) and is_word_spaced and not _opens_the_note_after(run, line)

    @staticmethod
    def _joined(run: LayerLine, line: LayerLine) -> LayerLine:
        box = Box.union([run.box, line.box])
        return LayerLine(f"{run.text.rstrip()} {line.text.lstrip()}", box.left, box.right, box.top, box.center)


def _in_reading_order(lines: list[LayerLine]) -> list[LayerLine]:
    rows: list[list[LayerLine]] = []
    for line in lines:
        if rows and _shares_a_row(rows[-1][0], line):
            rows[-1].append(line)
        else:
            rows.append([line])
    return [line for row in rows for line in sorted(row, key=lambda held: held.x0)]


def _opens_the_note_after(run: LayerLine, line: LayerLine) -> bool:
    run_number, line_number = (_note_number_opening(each) for each in (run, line))
    return run_number is not None and line_number == run_number + 1


def _note_number_opening(line: LayerLine) -> int | None:
    match = LAYER_LINE_OPENING_RE.match(line.text.strip())
    return int(match.group(1)) if match else None


class _LabelList:
    def __init__(self, lines: list[LayerLine]) -> None:
        margin = min((line.x0 for line in lines), default=0.0)
        at_the_margin = [line for line in lines if line.x0 <= margin + MARGIN_TOLERANCE_POINTS]
        self._labels = [line for line in at_the_margin if not _is_a_marginal_reference(line)]
        self._texts = [line for line in lines if line.x0 > margin + MARGIN_TOLERANCE_POINTS]

    def labels_wrapped_entries(self) -> bool:
        if not self._wraps_a_text_line() or not self._texts_meet_the_text_indent():
            return False
        return self._labels_open_entries()

    def _labels_open_entries(self) -> bool:
        right_edge = max(line.x1 for line in self._texts)
        labelled = [index for index, line in enumerate(self._texts) if _has_a_row_partner(line, self._labels)]
        opening = [index for index in labelled if index == 0 or _closes_an_entry(self._texts[index - 1], right_edge)]
        return len(opening) > len(labelled) / 2

    def _texts_meet_the_text_indent(self) -> bool:
        wrapped_starts = [line.x0 for line in self._wrapped_lines()]
        text_indent = min(wrapped_starts)
        if max(wrapped_starts) - text_indent > MARGIN_TOLERANCE_POINTS:
            return False
        return all(self._meets(line, text_indent) for line in self._texts)

    def _meets(self, line: LayerLine, text_indent: float) -> bool:
        starts_at_the_indent = abs(line.x0 - text_indent) <= MARGIN_TOLERANCE_POINTS
        runs_across_the_indent = line.x0 < text_indent < line.x1 and _has_a_row_partner(line, self._labels)
        return starts_at_the_indent or runs_across_the_indent

    def _wraps_a_text_line(self) -> bool:
        return bool(self._wrapped_lines())

    def _wrapped_lines(self) -> list[LayerLine]:
        return [line for line in self._texts if not _has_a_row_partner(line, self._labels)]


class _RunInLabelList:
    def __init__(self, lines: list[LayerLine]) -> None:
        self._lines = lines
        self._indent = max((line.x0 for line in lines), default=0.0)
        self._openings = [index for index, line in enumerate(lines) if not self._is_at_the_indent(line)]

    def labels_wrapped_entries(self) -> bool:
        enough_entries = len(self._openings) >= MIN_RUN_IN_ENTRIES
        return enough_entries and self._runs_its_openings_on() and self._opens_after_entry_ends()

    def _runs_its_openings_on(self) -> bool:
        run_on = [index for index in self._openings if self._runs_on_at_the_indent(index)]
        return len(run_on) > len(self._openings) / 2

    def _runs_on_at_the_indent(self, index: int) -> bool:
        following = index + 1
        ends_a_sentence = self._lines[index].text.rstrip().endswith(FULL_STOP)
        return following < len(self._lines) and self._is_at_the_indent(self._lines[following]) and not ends_a_sentence

    def _opens_after_entry_ends(self) -> bool:
        later = [index for index in self._openings if index > 0]
        closing = [index for index in later if _ends_on_closing_punctuation(self._lines[index - 1])]
        return len(closing) > len(later) / 2

    def _is_at_the_indent(self, line: LayerLine) -> bool:
        return line.x0 >= self._indent - MARGIN_TOLERANCE_POINTS


def _is_a_marginal_reference(line: LayerLine) -> bool:
    return MARGINAL_REFERENCE_RE.match(line.text.strip()) is not None


def _stand_as_columns(left: list[LayerLine], right: list[LayerLine]) -> bool:
    holds_enough_lines = min(len(left), len(right)) >= MIN_COLUMN_LINES
    leaves_a_gutter = max(line.x1 for line in left) < min(line.x0 for line in right)
    return holds_enough_lines and leaves_a_gutter and not _labels_the_entries_beside(left, right)


def _labels_the_entries_beside(left: list[LayerLine], right: list[LayerLine]) -> bool:
    every_line_beside_a_right_line = all(_has_a_row_partner(line, right) for line in left)
    run_on_lines = [line for line in right if not _has_a_row_partner(line, left)]
    return every_line_beside_a_right_line and len(run_on_lines) >= MIN_COLUMN_LINES and _sets_narrower(left, right)


def _sets_narrower(left: list[LayerLine], right: list[LayerLine]) -> bool:
    widths = [statistics.median(line.box.width for line in column) for column in (left, right)]
    return widths[0] < LABEL_WIDTH_SHARE * widths[1]


def _has_a_row_partner(line: LayerLine, others: list[LayerLine]) -> bool:
    return any(_shares_a_row(line, other) for other in others)


def _shares_a_row(first: LayerLine, second: LayerLine) -> bool:
    height = min(first.box.height, second.box.height)
    return abs(first.center[1] - second.center[1]) <= SAME_BASELINE_SHARE * height


def _line_pitch_of(lines: list[LayerLine]) -> float:
    pitches = [line.center[1] - previous.center[1] for previous, line in zip(lines, lines[1:])
               if not _shares_a_row(previous, line)]
    return statistics.median(pitches) if pitches else 0.0


def _opens_an_author_entry(line: LayerLine) -> bool:
    return bool(_ENTRY_OPENING_RE.match(line.text.strip()))


def _runs_a_sentence_on(previous: LayerLine, line: LayerLine) -> bool:
    runs_on_into_lowercase = not previous.text.rstrip().endswith(FULL_STOP) and _opens_lowercase(line.text)
    return runs_on_into_lowercase or _breaks_after_a_lowercase_word(previous)


def _breaks_after_a_lowercase_word(line: LayerLine) -> bool:
    return _opens_lowercase(line.text.split()[-1]) and not _ends_on_closing_punctuation(line)


def _opens_lowercase(text: str) -> bool:
    return text.strip()[:1].islower()


@dataclass(frozen=True)
class _LineStart:
    x0: float
    follows_an_entry_end: bool


class _ListShape:
    def __init__(self, lines: list[LayerLine], numbered_openings: set[int], right_edge: float) -> None:
        self._margin = min(line.x0 for line in lines)
        self._right_edge = right_edge
        self._indents = self._sets_a_hanging_indent(lines)
        self._numbered_openings = numbered_openings
        self._continuations_indented = not self._indents or self._runs_on_indented(lines)
        self._run_on_indent = self._run_on_indent_of(lines)
        self._indented_paragraphs = _FirstLineIndentedParagraphs(lines, self._margin, right_edge)
        self._starts = [_LineStart(line.x0, not self._runs_on(previous)) for previous, line in zip(lines, lines[1:])
                        if not _shares_a_row(previous, line) and self._shows_whether_its_entry_ends(previous)]
        self._pitch = _line_pitch_of(lines)

    def continues(self, index: int, previous: LayerLine | None, line: LayerLine) -> bool:
        if index in self._numbered_openings or previous is None or self._stands_a_blank_line_below(previous, line):
            return False
        if self._is_flush_and_numbered():
            return not self._opens_an_unlisted_number(previous, line)
        if self._indented_paragraphs.opens(line):
            return False
        if self._is_indented(line) == self._continuations_indented:
            return not self._opens_short_of_the_run_on_indent(previous, line)
        if self._is_indented(line) or not self._reaches_right_edge(previous):
            return False
        return self._may_run_on_flush(previous, line)

    def _stands_a_blank_line_below(self, previous: LayerLine, line: LayerLine) -> bool:
        return self._pitch > 0 and line.center[1] - previous.center[1] >= BLANK_LINE_PITCHES * self._pitch

    def _may_run_on_flush(self, previous: LayerLine, line: LayerLine) -> bool:
        continues_a_sentence = not self._indents or _runs_a_sentence_on(previous, line)
        continues_a_paragraph = continues_a_sentence or self._indented_paragraphs.runs_on_into(line)
        return continues_a_paragraph and not _opens_an_author_entry(line)

    def _opens_short_of_the_run_on_indent(self, previous: LayerLine, line: LayerLine) -> bool:
        if not self._continuations_indented or self._run_on_indent is None or _shares_a_row(previous, line):
            return False
        starts_short = line.x0 < self._run_on_indent - MARGIN_TOLERANCE_POINTS
        return starts_short and (not self._runs_on(previous) or self._opens_entries_at(line.x0))

    def _opens_entries_at(self, indent: float) -> bool:
        at_indent = [start for start in self._starts if abs(start.x0 - indent) <= MARGIN_TOLERANCE_POINTS]
        return sum(1 for start in at_indent if start.follows_an_entry_end) > len(at_indent) / 2

    def _shows_whether_its_entry_ends(self, line: LayerLine) -> bool:
        return not (self._runs_on(line) and _ends_on_closing_punctuation(line))

    def _run_on_indent_of(self, lines: list[LayerLine]) -> float | None:
        run_on_starts = [line.x0 for previous, line in zip(lines, lines[1:])
                         if self._runs_on(previous) and self._is_indented(line)]
        return statistics.median(run_on_starts) if run_on_starts else None

    def _is_flush_and_numbered(self) -> bool:
        return not self._indents and bool(self._numbered_openings)

    def _opens_an_unlisted_number(self, previous: LayerLine, line: LayerLine) -> bool:
        return bool(LAYER_LINE_OPENING_RE.match(line.text.strip())) and not self._reaches_right_edge(previous)

    def _runs_on_indented(self, lines: list[LayerLine]) -> bool:
        numbered = [line.x0 for index, line in enumerate(lines) if index in self._numbered_openings]
        others = [line.x0 for index, line in enumerate(lines) if index not in self._numbered_openings]
        if numbered and others:
            return statistics.median(numbered) <= statistics.median(others) + MARGIN_TOLERANCE_POINTS
        return not self._runs_on_flush(lines)

    def _runs_on_flush(self, lines: list[LayerLine]) -> bool:
        run_ons = [line for previous, line in zip(lines, lines[1:]) if self._runs_on(previous)]
        flush = sum(1 for line in run_ons if not self._is_indented(line))
        return flush >= MIN_FLUSH_RUN_ON_LINES and flush >= FLUSH_RUN_ON_SHARE * len(run_ons)

    def _runs_on(self, line: LayerLine) -> bool:
        return _runs_on(line, self._right_edge)

    def _sets_a_hanging_indent(self, lines: list[LayerLine]) -> bool:
        return self._indented_count(lines) >= len(lines) * HANGING_INDENT_SHARE or self._indents_only_its_run_ons(lines)

    def _indents_only_its_run_ons(self, lines: list[LayerLine]) -> bool:
        indented = [(previous, line) for previous, line in zip(lines, lines[1:]) if self._is_indented(line)]
        return bool(indented) and all(self._runs_on(previous) for previous, _line in indented)

    def _indented_count(self, lines: list[LayerLine]) -> int:
        return sum(1 for line in lines if self._is_indented(line))

    def _is_indented(self, line: LayerLine) -> bool:
        return line.x0 > self._margin + MARGIN_TOLERANCE_POINTS

    def _reaches_right_edge(self, line: LayerLine) -> bool:
        return _reaches(line, self._right_edge)


class _FirstLineIndentedParagraphs:
    def __init__(self, lines: list[LayerLine], margin: float, right_edge: float) -> None:
        self._lines = lines
        self._margin = margin
        self._right_edge = right_edge
        self._openings: set[LayerLine] = set()
        self._run_ons: set[LayerLine] = set()
        if self._punctuates_its_entry_ends():
            for index in range(1, len(lines) - 1):
                self._read_a_paragraph_at(index)

    def opens(self, line: LayerLine) -> bool:
        return line in self._openings

    def runs_on_into(self, line: LayerLine) -> bool:
        return line in self._run_ons

    def _punctuates_its_entry_ends(self) -> bool:
        entry_ends = [line for line in self._lines if not _runs_on(line, self._right_edge)]
        punctuated = sum(1 for line in entry_ends if _ends_on_closing_punctuation(line))
        return punctuated > len(entry_ends) / 2

    def _read_a_paragraph_at(self, index: int) -> None:
        previous, line, following = self._lines[index - 1:index + 2]
        closes_an_entry = _closes_an_entry(previous, self._right_edge)
        if closes_an_entry and self._is_indented(line) and self._runs_on_into(line, following):
            self._openings.add(line)
            self._run_ons.update(self._run_ons_after(index))

    def _run_ons_after(self, index: int) -> list[LayerLine]:
        run_ons = []
        for line, following in zip(self._lines[index:], self._lines[index + 1:]):
            if not self._runs_on_into(line, following):
                break
            run_ons.append(following)
        return run_ons

    def _runs_on_into(self, line: LayerLine, following: LayerLine) -> bool:
        runs_on_mid_sentence = _runs_on(line, self._right_edge) and not _ends_on_closing_punctuation(line)
        opens_flush = not self._is_indented(following) and not _shares_a_row(line, following)
        return runs_on_mid_sentence and opens_flush and not _opens_an_author_entry(following)

    def _is_indented(self, line: LayerLine) -> bool:
        return line.x0 > self._margin + MARGIN_TOLERANCE_POINTS


def _closes_an_entry(line: LayerLine, right_edge: float) -> bool:
    return not _runs_on(line, right_edge) or _ends_on_closing_punctuation(line)


def _ends_on_closing_punctuation(line: LayerLine) -> bool:
    return _CLOSING_PUNCTUATION_RE.search(line.text.rstrip()) is not None


def _runs_on(line: LayerLine, right_edge: float) -> bool:
    return _reaches(line, right_edge) or bool(_HYPHEN_END_RE.search(line.text.strip()))


def _reaches(line: LayerLine, right_edge: float) -> bool:
    return line.x1 >= right_edge - RIGHT_EDGE_TOLERANCE_POINTS


def _ends_together(end: float, other_end: float) -> bool:
    return abs(end - other_end) <= RIGHT_EDGE_TOLERANCE_POINTS


class _Numbering:
    def openings(self, lines: list[LayerLine]) -> set[int]:
        candidates = self._candidates(lines)
        longest = max((self._run_from(candidates, start) for start in range(len(candidates))), key=len, default=[])
        return set(longest) if self._numbers_the_entries(longest, lines) else set()

    @staticmethod
    def _numbers_the_entries(run: list[int], lines: list[LayerLine]) -> bool:
        right_edge = max((line.x1 for line in lines), default=0.0)
        after_a_run_on = sum(1 for index in run if index > 0 and _runs_on(lines[index - 1], right_edge))
        return len(run) >= MIN_NUMBERED_ENTRIES and after_a_run_on <= len(run) - after_a_run_on

    @staticmethod
    def _candidates(lines: list[LayerLine]) -> list[tuple[int, int]]:
        found = ((index, _note_number_opening(line)) for index, line in enumerate(lines))
        return [(index, number) for index, number in found
                if number is not None and not _stands_beside_an_unnumbered_label(lines, index)]

    @staticmethod
    def _run_from(candidates: list[tuple[int, int]], start: int) -> list[int]:
        index, number = candidates[start]
        run, expected = [index], number + 1
        for later_index, later_number in candidates[start + 1:]:
            if later_number == expected:
                run.append(later_index)
                expected += 1
        return run


def _stands_beside_an_unnumbered_label(lines: list[LayerLine], index: int) -> bool:
    line = lines[index]
    left_of_it = [other for other in lines[:index] if _shares_a_row(other, line) and other.x1 <= line.x0]
    return any(_note_number_opening(other) is None for other in left_of_it)
