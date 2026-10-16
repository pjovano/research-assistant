from __future__ import annotations

from collections import Counter
from functools import cached_property

from _extract.blocks import FOOTNOTE_KIND, HEADING_KIND, TEXT_KIND, Block
from _extract.blockwriting import HeadingReading
from _extract.candidates import CandidateBlock, CandidatePlace, HeadingCandidate
from _extract.dueoutline import DueOutline
from _extract.elements import Heading, Paragraph
from _extract.headings import (
    BARE_LABEL_RE, NO_KEY, RUN_IN_LABEL_RE, HeadingText, displayed_notation, ends_as_a_sentence, holds_only_notation,
    label_printed_before, reads_as_body_text,
)
from _extract.indenteddisplays import IndentedDisplays
from _extract.markdown import BOLD_MARK
from _extract.outline import Heading as OutlineHeading
from _extract.pagework import PageWork
from _extract.spans import PagePlace

LABEL_LEVEL = 1


class PageCandidates:
    def __init__(self, headings, page_input, reading: HeadingReading) -> None:
        self._opened, self._styles, self._work_title = headings.opened, headings.styles, headings.work_title
        self._running_heads = headings.running_heads.also(page_input.page.furniture_texts)
        self._page, self._folio = page_input.page, page_input.folio
        self._content, self._htmls = page_input.page.content, page_input.paired.body_texts
        self._reading = reading

    def heading_texts(self) -> list[str]:
        readings = [(block, self._reading.reading(block, html))
                    for block, html in zip(self._content, self._htmls) if block.kind == HEADING_KIND]
        return [reading.text for block, reading in readings if not self.repeats_the_running_head(block, reading)]

    def repeats_the_running_head(self, block: Block, reading: HeadingText) -> bool:
        return self._candidate_of(block, reading).repeats_running_head(self._opened, self._work_title)

    def is_new_heading(self, block: Block, reading: HeadingText) -> bool:
        opens_anew = self._page.stands_between_body_blocks(block) or not self._opened.names(reading.text)
        return opens_anew and self._candidate_of(block, reading).is_heading(self._opened, self._styles,
                                                                             self._work_title)

    def introduces_what_follows(self, block: Block, reading: HeadingText) -> bool:
        return self._candidate_of(block, reading).introduces_what_follows()

    def learn_the_style_of(self, block: Block) -> None:
        self._styles.learn(self._reading.key(block))

    def key_of(self, block: Block) -> tuple:
        return self._reading.key(block)

    def sits_in_an_indented_display(self, block: Block) -> bool:
        return IndentedDisplays(self._content).hold(block)

    def sets_in_the_body_type(self, block: Block, reading: HeadingText) -> bool:
        key = self._reading.key(block)
        if reading.is_display_lettering or key == NO_KEY:
            return False
        return key == self._body_key or self._measures_within_the_body_lines(block, key)

    def _measures_within_the_body_lines(self, block: Block, key: tuple) -> bool:
        if self._reading.trusts_the_layer(block.file_page) or not self._body_line_sizes:
            return False
        in_the_body_style = key[1:] == self._body_key[1:]
        return in_the_body_style and min(self._body_line_sizes) <= key[0] <= max(self._body_line_sizes)

    def sets_smaller_than_the_body_type(self, block: Block, reading: HeadingText) -> bool:
        key = self._reading.key(block)
        if reading.is_display_lettering or key == NO_KEY or self._body_key in (None, NO_KEY):
            return False
        return key[1:] == self._body_key[1:] and key[0] < self._body_key[0]

    @cached_property
    def _body_line_sizes(self) -> list[float]:
        return [size for block in self._content if block.kind == TEXT_KIND for size in self._reading.line_sizes(block)]

    @cached_property
    def _body_key(self) -> tuple | None:
        keys = [self._reading.key(block) for block in self._content if block.kind == TEXT_KIND]
        return Counter(keys).most_common(1)[0][0] if keys else None

    def _candidate_of(self, block: Block, reading: HeadingText) -> HeadingCandidate:
        place = CandidatePlace(self._folio_beside(block), self._page.stands_inside_the_text(block), block.bbox)
        return HeadingCandidate(CandidateBlock(reading, self._reading.key(block), place), self._running_heads)

    def _folio_beside(self, block: Block) -> str | None:
        return self._folio if self._sits_at_page_edge(block) else None

    def _sits_at_page_edge(self, block: Block) -> bool:
        body = [other for other in self._content if other.kind != FOOTNOTE_KIND] or [block]
        return block.bbox.top <= min(other.bbox.top for other in body) \
            or block.bbox.bottom >= max(other.bbox.bottom for other in body)


class HeadingBlocks:
    def __init__(self, work: PageWork, due: DueOutline, candidates: PageCandidates) -> None:
        self._texts, self._output, self._entries = work.texts, work.output, work.entries
        self._sublevel = work.sublevel
        self._due = due
        self._candidates = candidates
        self._rules = ((self._holds_only_notation, self._emit_formula),
                       (self._reads_as_body_text_in_the_body_type, self._emit_line),
                       (self._ends_as_a_sentence_below_the_body_type, self._emit_line),
                       (self._stays_bold, self._emit_bold), (self._is_bare_label, self._open_label),
                       (self._candidates.is_new_heading, self._open_candidate),
                       (self._candidates.introduces_what_follows, self._emit_line))

    def take(self, index: int, block: Block, _html: str) -> None:
        self._entries.flush()
        reading = self._texts.heading_reading_at(index)
        if self._candidates.repeats_the_running_head(block, reading):
            return
        matched = self._due.pending_matching(reading.text)
        if matched is not None:
            self._open_matched(index, block, matched)
        elif reading.text:
            self._output.hold_marks(list(reading.marks))
            self._apply_rule(index, block, reading)
        self._output.hold_marks([])

    def _open_matched(self, index: int, block: Block, matched: OutlineHeading) -> None:
        reading = self._texts.heading_reading_at(index)
        self._candidates.learn_the_style_of(block)
        self._open_the_label_printed_before(block, reading.text, matched)
        self._output.hold_marks(list(reading.marks))
        self._due.open_matched(index, block, matched)

    def _open_the_label_printed_before(self, block: Block, text: str, matched: OutlineHeading) -> None:
        label = label_printed_before(text, matched.title)
        if label is not None:
            self._output.open(Heading(matched.level, label, block.file_page, None), PagePlace.of_block(block))

    def _apply_rule(self, index: int, block: Block, reading: HeadingText) -> None:
        for applies, open_as in self._rules:
            if applies(block, reading):
                open_as(index, block, reading.text)
                return

    @staticmethod
    def _holds_only_notation(_block: Block, reading: HeadingText) -> bool:
        return holds_only_notation(reading.text)

    def _emit_formula(self, index: int, block: Block, text: str) -> None:
        self._emit_line(index, block, displayed_notation(text))

    def _reads_as_body_text_in_the_body_type(self, block: Block, reading: HeadingText) -> bool:
        return self._reads_as_body_text(block, reading) and self._candidates.sets_in_the_body_type(block, reading)

    def _ends_as_a_sentence_below_the_body_type(self, block: Block, reading: HeadingText) -> bool:
        return ends_as_a_sentence(reading.text) and self._candidates.sets_smaller_than_the_body_type(block, reading)

    def _reads_as_body_text(self, block: Block, reading: HeadingText) -> bool:
        return reads_as_body_text(reading.text) or self._candidates.sits_in_an_indented_display(block)

    def _emit_line(self, _index: int, block: Block, text: str) -> None:
        marks = "".join(self._output.taken_marks())
        self._output.emit([Paragraph(f"{text}{marks}", False, block.file_page)])

    def _stays_bold(self, _block: Block, reading: HeadingText) -> bool:
        return self._sublevel is None or RUN_IN_LABEL_RE.match(reading.text.strip()) is not None

    def _emit_bold(self, index: int, block: Block, text: str) -> None:
        self._emit_line(index, block, f"{BOLD_MARK}{text}{BOLD_MARK}")

    @staticmethod
    def _is_bare_label(_block: Block, reading: HeadingText) -> bool:
        return BARE_LABEL_RE.match(reading.text.strip()) is not None

    def _open_label(self, index: int, block: Block, text: str) -> None:
        title = self._due.merged_with_partner(text, self._due.merge_partner(index + 1))
        if not self._output.has_opened(title):
            self._output.open(Heading(LABEL_LEVEL, title, block.file_page, None), PagePlace.of_block(block))

    def _open_candidate(self, _index: int, block: Block, text: str) -> None:
        heading = Heading(self._sublevel, text, block.file_page, self._candidates.key_of(block))
        self._output.open(heading, PagePlace.of_block(block))
