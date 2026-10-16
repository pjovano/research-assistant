from __future__ import annotations

from dataclasses import dataclass

from _extract.blocks import (
    CAPTION_KIND, CODE_KIND, EQUATION_KIND, FOOTNOTE_KIND, HEADING_KIND, TABLE_KIND, TEXT_KIND, Block, PageBlocks,
)
from _extract.blocktexts import PageBlockTexts
from _extract.blockwriting import BlockWriting, HeadingReading
from _extract.candidates import HeadingStyles, OpenedHeadings, RunningHeads
from _extract.dueoutline import DueOutline
from _extract.elements import Heading, Paragraph
from _extract.entryblocks import EntryBlocks, PageSection
from _extract.footnotes import PairedPage, leading_note_number
from _extract.headingblocks import LABEL_LEVEL, HeadingBlocks, PageCandidates
from _extract.headings import HeadingMatch
from _extract.outline import Heading as OutlineHeading
from _extract.pageoutput import PageOutput
from _extract.pagework import PageWork
from _extract.policy import SectionPolicy
from _extract.statements import StatementLabel
from _extract.withheld import WithheldNote


@dataclass(frozen=True)
class HeadingComponents:
    policy: SectionPolicy
    match: HeadingMatch
    opened: OpenedHeadings
    styles: HeadingStyles
    work_title: str
    running_heads: RunningHeads


@dataclass(frozen=True)
class PageInput:
    page: PageBlocks
    paired: PairedPage
    due: list[OutlineHeading]
    sublevel: int | None
    folio: str | None = None


@dataclass(frozen=True)
class PageReaders:
    headings: HeadingReading
    blocks: BlockWriting


class PageElements:
    def __init__(self, readers: PageReaders, headings: HeadingComponents, page_input: PageInput) -> None:
        self._work = _page_work(readers, headings, page_input)
        self._policy, self._sublevel = headings.policy, page_input.sublevel
        self._reading, self._writing = readers.headings, readers.blocks
        candidates = PageCandidates(headings, page_input, readers.headings)
        self._due = DueOutline(self._work, page_input.due, candidates.heading_texts())
        self._headings = HeadingBlocks(self._work, self._due, candidates)
        self._kept_blocks: list[Block] = []
        self._labels = StatementLabel()
        self._takers = {HEADING_KIND: self._headings.take, EQUATION_KIND: self._take_equation}

    def built(self) -> list:
        for index, (block, html) in enumerate(self._work.texts.blocks_and_htmls()):
            self._due.open_due_above(block, index)
            self._take(index, block, html)
        self._work.entries.flush()
        self._due.open_the_rest()
        return self._work.output.elements()

    def kept_blocks(self) -> list[Block]:
        return list(self._kept_blocks)

    def withheld_entries(self) -> list[WithheldNote]:
        return self._work.entries.withheld()

    def _take(self, index: int, block: Block, html: str) -> None:
        if self._due.consumes(index) or block.kind == FOOTNOTE_KIND:
            return
        if self._policy.keeps_block(block):
            self._kept_blocks.append(block)
            self._takers.get(self._kind_of(index, block), self._take_body)(index, block, html)
        else:
            self._pass_over(block, html)

    def _kind_of(self, index: int, block: Block) -> str:
        return HEADING_KIND if self._divides_the_notes(index, block) else block.kind

    def _divides_the_notes(self, index: int, block: Block) -> bool:
        if not self._policy.in_note_list or block.kind != TEXT_KIND:
            return False
        unnumbered = leading_note_number(self._work.texts.plain_text_at(index)) is None
        return unnumbered and self._reading.sets_its_letters_in_small_capitals(block)

    def _pass_over(self, block: Block, html: str) -> None:
        self._work.entries.pass_over(block, self._writing.text_of(html))
        if block.kind == HEADING_KIND:
            self._due.pass_over(self._reading.text(block, html))

    def _take_equation(self, _index: int, block: Block, html: str) -> None:
        self._work.entries.flush()
        self._work.output.emit(self._writing.converted(block, html))

    def _take_body(self, index: int, block: Block, html: str) -> None:
        if self._holds_entries(block):
            self._work.entries.hold(block, html)
        else:
            self._work.entries.flush()
            converted = self._due.without_the_title_opening(index, self._writing.converted(block, html))
            self._work.output.emit(self._statement_headed(block, converted))

    def _holds_entries(self, block: Block) -> bool:
        if not _may_hold_entries(block):
            return False
        if _is_prose(block):
            return self._policy.in_entry_list or self._writing.sets_a_label_list(block)
        return self._policy.in_entry_list and self._writing.sets_a_label_list(block)

    def _statement_headed(self, block: Block, elements: list) -> list:
        if not _may_open_a_statement(block, elements):
            return elements
        label = self._labels.of(elements[0].text)
        if label is None:
            return elements
        remainder = self._labels.without(elements[0].text)
        heading = Heading(self._statement_level(), label, block.file_page, None)
        body = [Paragraph(remainder, elements[0].continues, block.file_page)] if remainder else []
        return [heading] + body + elements[1:]

    def _statement_level(self) -> int:
        return self._sublevel if self._sublevel is not None else LABEL_LEVEL


def _page_work(readers: PageReaders, headings: HeadingComponents, page_input: PageInput) -> PageWork:
    page = page_input.page
    texts = PageBlockTexts(page.content, page_input.paired.body_texts, readers.headings)
    output = PageOutput(headings.policy, headings.opened)
    entries = EntryBlocks(readers.blocks, output, PageSection(headings.policy, page.file_page))
    return PageWork(texts, output, entries, headings.policy, headings.match, page_input.sublevel)


def _may_open_a_statement(block: Block, elements: list) -> bool:
    return block.kind != CAPTION_KIND and bool(elements) and isinstance(elements[0], Paragraph)


def _may_hold_entries(block: Block) -> bool:
    return not block.is_image and block.kind != CODE_KIND


def _is_prose(block: Block) -> bool:
    return _may_hold_entries(block) and block.kind != TABLE_KIND
