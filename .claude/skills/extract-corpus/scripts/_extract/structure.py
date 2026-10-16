from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, field

from _extract.blockreading import BlockReading
from _extract.blocks import FOOTNOTE_KIND, Block, DocumentBlocks, PageBlocks
from _extract.blockwriting import BlockWriting, HeadingReading
from _extract.candidates import HeadingStyles, OpenedHeadings, RunningHeads
from _extract.carriednotes import CarriedMarks, CarriedNote
from _extract.elements import Heading, PageMarker, Paragraph, Verbatim
from _extract.endnotes import EndnoteSections
from _extract.footnotes import (
    FootnoteDefinition, FootnoteLabels, FootnoteLog, FootnotePairer, PairedPage, labelled_after_the_marked,
    leading_note_number, mark_numbers,
)
from _extract.footnotetexts import FootnoteTexts
from _extract.headband import RunningHeadBand
from _extract.headings import HeadingLevels, HeadingMatch, OutlineQueue, shape_of
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.lists import ListEntry
from _extract.outline import PAGE_TOP, Heading as OutlineHeading
from _extract.outlineplacement import OutlinePlacement
from _extract.page_elements import HeadingComponents, PageElements, PageInput, PageReaders
from _extract.pagerefiling import PageLayout, PageNotes
from _extract.parallelcolumns import ParallelColumns
from _extract.policy import SectionOpening, SectionPolicy
from _extract.readings import WorkerReadings
from _extract.runningheads import FurnitureProfile
from _extract.transcription import TranscribedBody
from _extract.withheld import WithheldMarks, WithheldNote

_FOOTNOTE_LABEL_RE = re.compile(r"\[\^(\d+)\]")

__all__ = ["Heading", "NoteStructure", "PageAssembler", "PageMarker", "Paragraph", "StructureInputs", "Verbatim",
           "WorkInputs", "shape_of"]


@dataclass
class PageResult:
    elements: list
    definitions: list[FootnoteDefinition]
    continuations: list[FootnoteDefinition]
    text: str
    layer_text: str


@dataclass(frozen=True)
class WorkInputs:
    layer: TextLayer
    block_html: BlockHtml
    fonts: object
    work_title: str = ""
    folios: dict[int, str | None] = field(default_factory=dict)
    pixel_pages: frozenset[int] = frozenset()
    furniture: list[str] = field(default_factory=list)
    furniture_profile: FurnitureProfile = field(default_factory=FurnitureProfile)


@dataclass(frozen=True)
class StructureInputs:
    blocks: DocumentBlocks
    outline: list[OutlineHeading]
    readings: WorkerReadings
    policy: SectionPolicy


class PageAssembler:
    def __init__(self, work: WorkInputs, policy: SectionPolicy, pairer: FootnotePairer) -> None:
        self._work = work
        self._policy = policy
        self._pairer = pairer
        self._reading = BlockReading(work)
        running_heads = RunningHeads(work.furniture, work.furniture_profile)
        self._headings = HeadingComponents(policy, HeadingMatch(), OpenedHeadings(), HeadingStyles(),
                                           work.work_title, running_heads)
        self._layout = PageLayout(work, running_heads, policy)
        self._notes = PageNotes(self._reading, running_heads, pairer)
        self._footnote_texts = FootnoteTexts(self._reading, policy)
        self._readers = PageReaders(HeadingReading(work.layer, self._reading), BlockWriting(work.layer, self._reading))
        self._withheld: list[WithheldNote] = []

    def assemble(self, page: PageBlocks, due: list[OutlineHeading], sublevel: int | None) -> PageResult:
        page = self._notes.refiled(self._layout.refiled(page), self._list_top(due))
        self._readers.blocks.read_page(page.content)
        paired = self._paired(page)
        folio = self.folio_of(page.file_page)
        page_elements = PageElements(self._readers, self._headings, PageInput(page, paired, due, sublevel, folio))
        elements = [PageMarker(page.file_page, folio)] + page_elements.built()
        self._withheld += self._withheld_notes(page) + page_elements.withheld_entries()
        continuations = self._pairer.continuations()
        self._pairer.clear_continuations()
        output_text = "\n".join([_joined_text(elements)] + paired.footnote_texts())
        return PageResult(elements, paired.definitions, continuations, output_text,
                          self._layer_text_of(page.file_page, self._measured_blocks(page, page_elements)))

    def _paired(self, page: PageBlocks) -> PairedPage:
        htmls = [self._reading.body_html(block) for block in page.content]
        paired = self._pairer.paired(page.file_page, htmls, self._footnote_texts.of(page))
        self._pairer.close_marks(self._marks_only_the_scope_cuts(page.content, htmls))
        return paired

    def _marks_only_the_scope_cuts(self, blocks: list[Block], htmls: list[str]) -> set[str]:
        kept = [self._policy.keeps_block(block) for block in blocks]
        cut_marks = {number for html, is_kept in zip(htmls, kept) if not is_kept for number in mark_numbers(html)}
        kept_marks = {number for html, is_kept in zip(htmls, kept) if is_kept for number in mark_numbers(html)}
        return cut_marks - kept_marks

    def _list_top(self, due: list[OutlineHeading]) -> float | None:
        return PAGE_TOP if self._policy.in_note_list and not due else None

    def withheld_notes(self) -> list[WithheldNote]:
        return list(self._withheld)

    def carried_notes(self) -> list[CarriedNote]:
        return self._pairer.carried_notes()

    def notation_log(self) -> list[str]:
        return self._reading.notation_log()

    def hanging_entries(self, file_page: int, blocks: list[Block]) -> list[ListEntry]:
        return self._readers.blocks.hanging_entries(file_page, blocks)

    def _withheld_notes(self, page: PageBlocks) -> list[WithheldNote]:
        in_note_list = self._policy.in_note_list
        withheld = [block for block in page.content if not self._policy.keeps_block(block)
                    and (block.kind == FOOTNOTE_KIND or in_note_list)]
        numbered = [(block, leading_note_number(self._readers.blocks.text_of(self._reading.html_of(block))))
                    for block in withheld]
        return [WithheldNote(page.file_page, number, block.kind != FOOTNOTE_KIND) for block, number in numbered
                if number]

    def transcribed(self, page: PageBlocks, text: str, due: list[OutlineHeading]) -> PageResult:
        body = TranscribedBody(text.strip(), page.file_page, self._headings.match)
        elements = [PageMarker(page.file_page, self.folio_of(page.file_page))]
        elements += self._kept(body.elements(due, self._opened_outline))
        return PageResult(elements, [], [], text, text)

    def omitted(self, due: list[OutlineHeading]) -> PageResult:
        return PageResult(self._kept([self._opened_outline(heading) for heading in due]), [], [], "", "")

    def _opened_outline(self, heading: OutlineHeading) -> Heading:
        self._policy.opens(SectionOpening(heading.level, heading.title))
        if self._policy.keeps_page(heading.file_page):
            self._headings.opened.add(heading.title, heading.level)
        return Heading(heading.level, heading.title, heading.file_page, None)

    @staticmethod
    def _measured_blocks(page: PageBlocks, page_elements: PageElements) -> list[Block]:
        kept = page_elements.kept_blocks()
        return kept + page.of_kind(FOOTNOTE_KIND) if kept else kept

    def _layer_text_of(self, file_page: int, blocks: list[Block]) -> str:
        chars = [char for block in blocks for char in self._work.layer.chars_in(file_page, block.bbox)]
        return "".join(char.char for char in chars if not self._work.fonts.is_math(char.font))

    def _kept(self, elements: list) -> list:
        return [element for element in elements if self._policy.keeps_page(element.file_page)]

    def folio_of(self, file_page: int) -> str | None:
        return self._work.folios.get(file_page)


class NoteStructure:
    def __init__(self, work: WorkInputs, inputs: StructureInputs) -> None:
        self._blocks = ParallelColumns(work).refiled(inputs.blocks)
        self._readings = inputs.readings
        placement = OutlinePlacement(inputs.blocks.pages, HeadingMatch(), inputs.policy)
        self._queue = OutlineQueue(placement.placed(inputs.outline))
        self._log = FootnoteLog()
        head_band = RunningHeadBand.of(self._blocks, work.layer)
        banded = dataclasses.replace(work, furniture_profile=work.furniture_profile.with_head_band(head_band))
        self._assembler = PageAssembler(banded, inputs.policy, FootnotePairer(FootnoteLabels(), self._log))
        self._elements: list = []
        self._definitions: list[FootnoteDefinition] = []
        self._page_texts: dict[int, str] = {}
        self._layer_texts: dict[int, str] = {}
        self._assembled = False

    def elements(self) -> list:
        self._assemble()
        return list(self._elements)

    def definitions(self) -> list[FootnoteDefinition]:
        self._assemble()
        texts = [_text_of(element) for element in self._elements]
        referenced = {int(label) for text in texts for label in _FOOTNOTE_LABEL_RE.findall(text)}
        unpaired_marks = {int(number) for text in texts for number in mark_numbers(text)}
        kept = [definition for definition in self._definitions
                if not definition.marked or definition.label in referenced]
        unrepeated = [definition for definition in kept if not any(map(definition.repeats_the_opening_of, kept))]
        return labelled_after_the_marked(unrepeated, unpaired_marks)

    def page_texts(self) -> dict[int, str]:
        self._assemble()
        return dict(self._page_texts)

    def layer_text(self, file_page: int) -> str:
        self._assemble()
        return self._layer_texts.get(file_page, "")

    def footnote_log(self) -> list[str]:
        self._assemble()
        return self._log.entries_outside(EndnoteSections(self._elements))

    def notation_log(self) -> list[str]:
        self._assemble()
        return self._assembler.notation_log()

    def _assemble(self) -> None:
        if self._assembled:
            return
        for page in self._blocks.pages:
            self._take(page, self._result_for(page))
        levelled = HeadingLevels().levelled(self._elements)
        withheld = WithheldMarks(self._assembler.withheld_notes(), EndnoteSections(levelled))
        self._elements = CarriedMarks(self._assembler.carried_notes()).linked(withheld.removed(levelled))
        self._assembled = True

    def _result_for(self, page: PageBlocks) -> PageResult:
        reading = self._readings.for_page(page.file_page)
        due = self._queue.due_on(page.file_page)
        self._queue.release(page.file_page)
        if reading is not None and reading.unreadable:
            return self._assembler.omitted(due)
        if reading is not None:
            return self._assembler.transcribed(page, reading.text, due)
        return self._assembler.assemble(page, due, self._queue.sublevel)

    def _take(self, page: PageBlocks, result: PageResult) -> None:
        self._elements.extend(result.elements)
        for continued in result.continuations:
            self._definitions = [continued if held.is_continued_as(continued) else held for held in self._definitions]
        self._definitions.extend(result.definitions)
        self._page_texts[page.file_page] = result.text
        self._layer_texts[page.file_page] = result.layer_text


def _joined_text(elements: list) -> str:
    return "\n".join(part for part in map(_text_of, elements) if part)


def _text_of(element) -> str:
    return getattr(element, "text", None) or getattr(element, "title", None) or ""
