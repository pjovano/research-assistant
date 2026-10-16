from __future__ import annotations

import dataclasses

from _extract.blockreading import BlockReading
from _extract.blocks import FOOTER_KIND, HEADING_KIND, Block, PageBlocks
from _extract.enclosedheadings import EnclosedHeadings
from _extract.footernotes import FooterNotes
from _extract.footnotes import FootnotePairer, mark_numbers
from _extract.headings import HeadingKey
from _extract.layerlines import PageLines
from _extract.notetails import NoteTypeTails
from _extract.order import SingleColumnOrder
from _extract.policy import SectionPolicy
from _extract.runningheads import CandidatePlace, HeadPrinting, RepeatedTitles, RunningHeads
from _extract.scopecuts import ScopeCuts
from _extract.strays import CarriedNotes, CarriedOver, DisplayedLines, PageTypesetting, StrayFootnotes
from _extract.twins import EngineTwins, NoteTwins
from _extract.typesizes import LinePitch, TypeSize


class PageLayout:
    def __init__(self, work, running_heads: RunningHeads, policy: SectionPolicy) -> None:
        self._layer = work.layer
        self._policy = policy
        self._pixel_pages = work.pixel_pages
        self._running_heads = running_heads
        self._keys = HeadingKey(work.layer)

    def refiled(self, page: PageBlocks) -> PageBlocks:
        lifted = self._headings_lifted(page.file_page, self._read_once(page))
        blocks = self._cut_at_the_scope(page.file_page, lifted)
        ordered = SingleColumnOrder(PageLines(self._layer, page.file_page, blocks)).ordered(blocks)
        refiled = PageBlocks(page.file_page, ordered)
        return PageBlocks(page.file_page, [self._as_furniture(refiled, block) for block in ordered])

    def _read_once(self, page: PageBlocks) -> list[Block]:
        blocks = EngineTwins(page.blocks).without(page.blocks)
        if page.file_page in self._pixel_pages:
            return blocks
        return NoteTwins(PageLines(self._layer, page.file_page, blocks)).without(blocks)

    def _headings_lifted(self, file_page: int, blocks: list[Block]) -> list[Block]:
        if file_page in self._pixel_pages:
            return blocks
        return EnclosedHeadings(PageLines(self._layer, file_page, blocks)).split(blocks)

    def _cut_at_the_scope(self, file_page: int, blocks: list[Block]) -> list[Block]:
        cuts = self._policy.cuts_on(file_page)
        if file_page in self._pixel_pages or not cuts:
            return blocks
        return ScopeCuts(PageLines(self._layer, file_page, blocks), cuts).split(blocks)

    def _as_furniture(self, page: PageBlocks, block: Block) -> Block:
        if block.is_furniture or not self._running_heads.is_running_head(self._printing(page, block),
                                                                         RepeatedTitles.none()):
            return block
        return dataclasses.replace(block, kind=FOOTER_KIND)

    def _printing(self, page: PageBlocks, block: Block) -> HeadPrinting:
        size = self._keys.of(block)[0] if block.kind == HEADING_KIND else None
        return HeadPrinting(block.plain_text, size, CandidatePlace(inside_the_text=page.stands_inside_the_text(block), box=block.bbox))


class PageNotes:
    def __init__(self, reading: BlockReading, running_heads: RunningHeads, pairer: FootnotePairer) -> None:
        self._reading = reading
        self._running_heads = running_heads
        self._pairer = pairer

    def refiled(self, page: PageBlocks, list_top: float | None) -> PageBlocks:
        page = self._with_note_tails_parted(self._with_footer_notes(page))
        self._reading.read_page(page)
        return self._with_stray_footnotes(page, CarriedOver(list_top, self._pairer.open_marks_before(page.file_page)))

    def _with_footer_notes(self, page: PageBlocks) -> PageBlocks:
        self._reading.read_page(page)
        marks = {number for block in page.content for number in mark_numbers(self._reading.html_of(block))}
        notes = FooterNotes(self._running_heads, self._reading.lines, marks)
        return PageBlocks(page.file_page, notes.refiled(page.blocks))

    def _with_note_tails_parted(self, page: PageBlocks) -> PageBlocks:
        self._reading.read_page(page)
        if self._reading.reads_pixels:
            return page
        return PageBlocks(page.file_page, NoteTypeTails(self._reading.lines, page.blocks).parted(page.blocks))

    def _with_stray_footnotes(self, page: PageBlocks, carried: CarriedOver) -> PageBlocks:
        strays = StrayFootnotes(page.content, self._htmls(page.content), carried)
        listed = strays.reclassified(page.blocks)
        reclassified = PageBlocks(page.file_page, listed)
        sizes = self._type_sizes(reclassified.content)
        typesetting = PageTypesetting(sizes, self._pairer.leaves_a_note_unfinished_before(page.file_page),
                                      self._line_counts(reclassified.content), self._line_pitches(reclassified.content))
        notes = CarriedNotes(reclassified.content, self._htmls(reclassified.content), typesetting)
        carried_page = PageBlocks(page.file_page, notes.reclassified(reclassified.blocks))
        displayed = DisplayedLines(carried_page.content, self._htmls(carried_page.content), sizes)
        return PageBlocks(page.file_page, displayed.reclassified(carried_page.blocks))

    def _htmls(self, blocks: list[Block]) -> list[str]:
        return [self._reading.html_of(block) for block in blocks]

    def _line_counts(self, blocks: list[Block]) -> dict[str, int]:
        return self._measured(blocks, len)

    def _type_sizes(self, blocks: list[Block]) -> dict[str, float]:
        return self._measured(blocks, lambda rows: TypeSize(rows).median())

    def _line_pitches(self, blocks: list[Block]) -> dict[str, float]:
        return self._measured(blocks, lambda rows: LinePitch(rows).median())

    def _measured(self, blocks: list[Block], measure) -> dict:
        measures = {block.identifier: measure(self._reading.lines.of(block)) for block in blocks}
        return {identifier: value for identifier, value in measures.items() if value is not None}
