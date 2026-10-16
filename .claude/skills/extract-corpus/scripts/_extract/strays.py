from __future__ import annotations

import dataclasses
import re
import statistics
from dataclasses import dataclass

from _extract.blockreading import BlockReading
from _extract.blocks import EQUATION_KIND, FOOTNOTE_KIND, HEADING_KIND, LIST_ITEM_KIND, TEXT_KIND, Block
from _extract.footnotes import MARK_RE, leading_note_number, mark_numbers
from _extract.lists import MARGIN_TOLERANCE_POINTS
from _extract.notenumbers import NOTE_SYMBOLS, SIGN_OPENING_RE
from _extract.policy import is_notes_heading
from _extract.sentences import breaks_off_mid_sentence, closes_a_sentence

STRAY_KINDS = (TEXT_KIND, EQUATION_KIND)
NOTE_READING_KINDS = STRAY_KINDS + (LIST_ITEM_KIND,)
NOTE_TYPE_KINDS = STRAY_KINDS + (HEADING_KIND,)
STACKED_OVERLAP_POINTS = 4.0
NOTE_TYPE_SHARE = 0.9
NOTE_SIZE_TOLERANCE_POINTS = 0.5
NOTE_PITCH_TOLERANCE_POINTS = 0.5
_RAISED_SYMBOLS_RE = re.compile(rf"<sup>\s*([{NOTE_SYMBOLS}]+)\s*</sup>")
_DISPLAYED_LABEL_RE = re.compile(r"^\s*([(\[](?P<number>\d{1,3})[)\]])\s")
_SUPERSCRIPT_DIGITS_RE = re.compile("[⁰¹²³⁴⁵⁶⁷⁸⁹]+")
_SUPERSCRIPT_TO_DIGITS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")


@dataclass(frozen=True)
class CarriedOver:
    list_top: float | None = None
    open_marks: frozenset[str] = frozenset()


class StrayFootnotes:
    def __init__(self, content: list[Block], htmls: list[str], carried: CarriedOver = CarriedOver()) -> None:
        self._content = [(block, html) for block, html in zip(content, htmls) if _text_of(block, html)]
        self._footnote_boxes = [block.bbox for block in content if block.kind == FOOTNOTE_KIND]
        self._open_marks = carried.open_marks
        self._notes_list_top = min(self._notes_list_tops(carried.list_top), default=None)
        self._numbered = [block for block, html in self._content if self._is_numbered_like_a_mark(block, html)]
        self._zone_top = min((block.bbox.top for block in self._numbered if self._opens_the_footnotes(block)),
                             default=None)

    def _notes_list_tops(self, carried_list_top: float | None) -> list[float]:
        other_headings = [block for block, html in self._content
                          if block.kind == HEADING_KIND and not is_notes_heading(_text_of(block, html))]
        tops = [block.bbox.bottom for block, html in self._content if _heads_a_notes_list(block, _text_of(block, html))]
        opens_no_other_section = not other_headings
        carried = [carried_list_top] if carried_list_top is not None and opens_no_other_section else []
        return tops + carried

    def reclassified(self, blocks: list[Block]) -> list[Block]:
        refiled = [self._reclassified(block) for block in blocks]
        listed = [after for before, after in zip(blocks, refiled) if self._is_listed_endnote(before)]
        return _ListedEndnotes(listed).placed(refiled)

    def _reclassified(self, block: Block) -> Block:
        if self._is_stray(block):
            return dataclasses.replace(block, kind=FOOTNOTE_KIND)
        if self._is_listed_endnote(block):
            return dataclasses.replace(block, kind=TEXT_KIND)
        return block

    def _is_listed_endnote(self, block: Block) -> bool:
        return block.kind == FOOTNOTE_KIND and self._lists_an_endnote(block)

    def _is_stray(self, block: Block) -> bool:
        is_below_the_zone = self._zone_top is not None and self._lies_below(block, self._zone_top)
        return block.kind in NOTE_READING_KINDS and (is_below_the_zone or self._lies_between_footnotes(block))

    def _lies_between_footnotes(self, block: Block) -> bool:
        column = [box for box in self._footnote_boxes if box.shares_a_column_with(block.bbox)]
        has_one_above = any(self._lies_below(block, box.bottom) for box in column)
        has_one_below = any(box.top + STACKED_OVERLAP_POINTS >= block.bbox.bottom for box in column)
        return has_one_above and has_one_below and not self._lists_an_endnote(block)

    def _is_numbered_like_a_mark(self, block: Block, html: str) -> bool:
        sign = SIGN_OPENING_RE.match(_text_of(block, html))
        is_marked = sign is not None and self._is_marked_elsewhere(block, sign.group(1))
        return block.kind in NOTE_READING_KINDS and is_marked and not self._lists_an_endnote(block)

    def _lists_an_endnote(self, block: Block) -> bool:
        return self._notes_list_top is not None and self._lies_below(block, self._notes_list_top)

    def _is_marked_elsewhere(self, block: Block, sign: str) -> bool:
        raised_on_the_page = any(sign in _raised_signs(html) for other, html in self._content if other != block)
        return raised_on_the_page or (sign in self._open_marks and self._lies_below_the_body(block))

    def _lies_below_the_body(self, block: Block) -> bool:
        return any(SIGN_OPENING_RE.match(_text_of(other, html)) is None for other, html in self._content
                   if other.bbox.bottom <= block.bbox.top + STACKED_OVERLAP_POINTS)

    def _opens_the_footnotes(self, opening: Block) -> bool:
        return all(self._belongs_below(opening, other) for other in self._blocks_reaching_below(opening))

    def _blocks_reaching_below(self, opening: Block) -> list[Block]:
        return [block for block, _html in self._content if block != opening and block.kind != FOOTNOTE_KIND
                and block.bbox.bottom > opening.bbox.top + STACKED_OVERLAP_POINTS]

    def _belongs_below(self, opening: Block, other: Block) -> bool:
        return other in self._numbered or self._continues_below(opening, other)

    def _continues_below(self, opening: Block, other: Block) -> bool:
        read_as_a_footnote = any(other.bbox.shares_a_region_with(box) for box in self._footnote_boxes)
        return other.kind in STRAY_KINDS and read_as_a_footnote and self._lies_below(other, opening.bbox.bottom)

    @staticmethod
    def _lies_below(block: Block, edge: float) -> bool:
        return block.bbox.top + STACKED_OVERLAP_POINTS >= edge


class _ListedEndnotes:
    def __init__(self, endnotes: list[Block]) -> None:
        self._endnotes = endnotes

    def placed(self, blocks: list[Block]) -> list[Block]:
        listed = [index for index, block in enumerate(blocks) if block in self._endnotes]
        if not listed:
            return blocks
        first = blocks[listed[0]]
        above = [index for index in range(listed[0]) if _lies_above_in_the_column_of(blocks[index], first)]
        if not above:
            return blocks
        between = blocks[above[-1] + 1:listed[0]]
        beside = [block for block in between if not block.bbox.shares_a_column_with(first.bbox)]
        kept = [block for block in blocks if block not in beside]
        after = kept.index(blocks[listed[-1]]) + 1
        return kept[:after] + beside + kept[after:]


def _lies_above_in_the_column_of(block: Block, endnote: Block) -> bool:
    lies_above = block.bbox.bottom <= endnote.bbox.top + STACKED_OVERLAP_POINTS
    return block.bbox.shares_a_column_with(endnote.bbox) and lies_above


def _opens_on_a_sign(text: str) -> bool:
    return SIGN_OPENING_RE.match(text) is not None or leading_note_number(text) is not None


def _text_of(block: Block, html: str) -> str:
    return dataclasses.replace(block, html=html).plain_text or block.plain_text


def _raised_signs(html: str) -> set[str]:
    return set(mark_numbers(html)) | set(_RAISED_SYMBOLS_RE.findall(html))


def _superscript_marks(html: str, text: str) -> set[str]:
    raised = {digits.translate(_SUPERSCRIPT_TO_DIGITS) for digits in _SUPERSCRIPT_DIGITS_RE.findall(text)}
    return set(mark_numbers(html)) | raised


def _may_carry_a_note(block: Block) -> bool:
    return block.kind in NOTE_TYPE_KINDS or BlockReading.is_table(block)


def _heads_a_notes_list(block: Block, text: str) -> bool:
    return block.kind == HEADING_KIND and is_notes_heading(text)


@dataclass(frozen=True)
class PageTypesetting:
    sizes: dict[str, float]
    unfinished_note_before: bool = False
    line_counts: dict[str, int] = dataclasses.field(default_factory=dict)
    pitches: dict[str, float] = dataclasses.field(default_factory=dict)


class CarriedNotes:
    def __init__(self, content: list[Block], htmls: list[str], typesetting: PageTypesetting) -> None:
        self._content = content
        self._settings = (_NoteSetting(content, typesetting.sizes, NOTE_SIZE_TOLERANCE_POINTS),
                          _NoteSetting(content, typesetting.pitches, NOTE_PITCH_TOLERANCE_POINTS))
        self._line_counts = typesetting.line_counts
        self._unfinished_note_before = typesetting.unfinished_note_before
        self._text_margin = min((block.bbox.left for block in content if block.kind in NOTE_READING_KINDS
                                 or block.kind == FOOTNOTE_KIND), default=None)
        self._notes_top = min((block.bbox.top for block in content if block.kind == FOOTNOTE_KIND), default=None)
        self._marks = {block.identifier: set(mark_numbers(html)) for block, html in zip(content, htmls)}
        self._texts = {block.identifier: _text_of(block, MARK_RE.sub("", html)) for block, html in zip(content, htmls)}
        self._openings = {block.identifier: leading_note_number(_text_of(block, html))
                          for block, html in zip(content, htmls)}
        self._note_numerals = {self._openings[block.identifier] for block in content
                               if block.kind == FOOTNOTE_KIND} - {None}
        self._signed = {block.identifier for block, html in zip(content, htmls)
                        if _opens_on_a_sign(_text_of(block, html))}

    def reclassified(self, blocks: list[Block]) -> list[Block]:
        carried: set[str] = set()
        for block in sorted(self._content, key=lambda block: block.bbox.top, reverse=True):
            if self._carries_a_note(block, carried):
                carried.add(block.identifier)
        return [self._refiled(block, carried) for block in blocks]

    def _refiled(self, block: Block, carried: set[str]) -> Block:
        if block.identifier in carried:
            return dataclasses.replace(block, kind=FOOTNOTE_KIND)
        if self._is_a_quotation_read_as_a_note(block):
            return dataclasses.replace(block, kind=TEXT_KIND)
        return block

    def _is_a_quotation_read_as_a_note(self, block: Block) -> bool:
        is_unsigned = block.identifier not in self._signed
        return block.kind == FOOTNOTE_KIND and is_unsigned and self._is_a_block_quotation(block)

    def _carries_a_note(self, block: Block, carried: set[str]) -> bool:
        if not _may_carry_a_note(block) or self._is_refused(block):
            return False
        if self._notes_top is None:
            return self._carries_a_note_on_a_page_without_notes(block, carried)
        return self._sits_above_the_notes(block, carried) and self._is_set_in_note_type(block)

    def _is_refused(self, block: Block) -> bool:
        return any(refusal(block) for refusal in (self._raises_a_mark_the_notes_answer, self._opens_a_section,
                                                   self._is_a_block_quotation))

    def _carries_a_note_on_a_page_without_notes(self, block: Block, carried: set[str]) -> bool:
        is_the_lowest_uncarried = all(other.bbox.top <= block.bbox.top or other.identifier in carried
                                      for other in self._content)
        is_out_of_the_reading = (self._unfinished_note_before or self._is_a_note_below_a_broken_off_sentence(block)
                                 or self._answers_a_mark_raised_above(block))
        return is_out_of_the_reading and is_the_lowest_uncarried and self._is_set_below_body_type(block)

    def _answers_a_mark_raised_above(self, block: Block) -> bool:
        above = [other for other in self._content if other.bbox.bottom <= block.bbox.top + STACKED_OVERLAP_POINTS]
        raised_above = {mark for other in above for mark in self._marks[other.identifier]}
        return self._openings[block.identifier] in raised_above

    def _is_a_note_below_a_broken_off_sentence(self, block: Block) -> bool:
        nearest = self._nearest_above(block)
        if nearest is None or nearest.kind != TEXT_KIND:
            return False
        breaks_off = breaks_off_mid_sentence(self._texts[nearest.identifier])
        return breaks_off and closes_a_sentence(self._texts[block.identifier])

    def _opens_a_section(self, block: Block) -> bool:
        nearest = self._nearest_above(block)
        return nearest is not None and nearest.kind == HEADING_KIND and not self._is_set_in_note_type(nearest)

    def _nearest_above(self, block: Block) -> Block | None:
        above = [other for other in self._content if other.bbox.bottom <= block.bbox.top + STACKED_OVERLAP_POINTS]
        return max(above, key=lambda other: other.bbox.bottom, default=None)

    def _is_a_block_quotation(self, block: Block) -> bool:
        is_indented = self._text_margin is not None and block.bbox.left > self._text_margin + MARGIN_TOLERANCE_POINTS
        spans_lines = self._line_counts.get(block.identifier, 0) > 1
        return is_indented and spans_lines and self._lies_above_the_notes(block) and not self._unfinished_note_before

    def _lies_above_the_notes(self, block: Block) -> bool:
        other_notes = [other.bbox.top for other in self._content if other.kind == FOOTNOTE_KIND and other is not block]
        return not other_notes or block.bbox.top + STACKED_OVERLAP_POINTS < min(other_notes)

    def _raises_a_mark_the_notes_answer(self, block: Block) -> bool:
        return not self._note_numerals.isdisjoint(self._marks[block.identifier])

    def _sits_above_the_notes(self, block: Block, carried: set[str]) -> bool:
        body_below = [other for other in self._content if other.kind != FOOTNOTE_KIND
                      and other.identifier not in carried and other.bbox.top > block.bbox.top]
        return not body_below and self._reaches_the_notes(block, carried)

    def _reaches_the_notes(self, block: Block, carried: set[str]) -> bool:
        tops = [self._notes_top] + [other.bbox.top for other in self._content if other.identifier in carried]
        lies_among_the_notes = block.bbox.top + STACKED_OVERLAP_POINTS >= self._notes_top
        return lies_among_the_notes or block.bbox.bottom <= min(tops) + STACKED_OVERLAP_POINTS

    def _is_set_in_note_type(self, block: Block) -> bool:
        return any(setting.sets_in_note_type(block) for setting in self._settings)

    def _is_set_below_body_type(self, block: Block) -> bool:
        return any(setting.sets_below_the_body(block) for setting in self._settings)


class _NoteSetting:
    def __init__(self, content: list[Block], measures: dict[str, float], tolerance: float) -> None:
        self._content = content
        self._measures = measures
        self._tolerance = tolerance

    def sets_in_note_type(self, block: Block) -> bool:
        measure = self._measures.get(block.identifier)
        notes = self._measures_of(lambda other: other.kind == FOOTNOTE_KIND)
        if measure is None or not notes:
            return False
        matches_the_notes = abs(measure - statistics.median(notes)) <= self._tolerance
        return matches_the_notes and self.sets_below_the_body(block)

    def sets_below_the_body(self, block: Block) -> bool:
        measure = self._measures.get(block.identifier)
        body = self._measures_of(lambda other: other is not block and other.kind in STRAY_KINDS)
        return measure is not None and bool(body) and measure < NOTE_TYPE_SHARE * statistics.median(body)

    def _measures_of(self, chosen) -> list[float]:
        return [self._measures[other.identifier] for other in self._content
                if chosen(other) and other.identifier in self._measures]


class DisplayedLines:
    def __init__(self, content: list[Block], htmls: list[str], type_sizes: dict[str, float]) -> None:
        self._texts = {block.identifier: _text_of(block, html) for block, html in zip(content, htmls)}
        self._body_marks = {mark for block, html in zip(content, htmls) if block.kind in STRAY_KINDS
                            for mark in _superscript_marks(html, self._texts[block.identifier])}
        self._content = content
        self._sizes = type_sizes
        body = [type_sizes[block.identifier] for block in content
                if block.kind in STRAY_KINDS and block.identifier in type_sizes]
        self._body_size = statistics.median(body) if body else None

    def reclassified(self, blocks: list[Block]) -> list[Block]:
        return [dataclasses.replace(block, kind=TEXT_KIND) if self._is_displayed(block) else block for block in blocks]

    def _is_displayed(self, block: Block) -> bool:
        label = _DISPLAYED_LABEL_RE.match(self._texts.get(block.identifier, ""))
        if block.kind != FOOTNOTE_KIND or label is None:
            return False
        is_marked = self._is_marked_in_the_body(label.group(1)) or label.group("number") in self._body_marks
        return self._is_set_in_body_type(block) and not is_marked

    def _is_set_in_body_type(self, block: Block) -> bool:
        size = self._sizes.get(block.identifier)
        return size is not None and self._body_size is not None and size >= NOTE_TYPE_SHARE * self._body_size

    def _is_marked_in_the_body(self, label: str) -> bool:
        return any(label in self._texts[block.identifier] for block in self._content if block.kind in STRAY_KINDS)
