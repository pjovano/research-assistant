from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from _extract.blocks import Block
from _extract.blockwriting import BlockWriting
from _extract.elements import LIST_ITEM_BULLET, Paragraph, Verbatim
from _extract.entryopenings import LayerEntryOpenings
from _extract.footnotes import leading_note_number
from _extract.lists import ListEntry
from _extract.pageoutput import PageOutput
from _extract.policy import SectionPolicy
from _extract.scopecuts import is_a_scope_piece
from _extract.withheld import WithheldNote


@dataclass(frozen=True)
class PageSection:
    policy: SectionPolicy
    file_page: int


class EntryBlocks:
    def __init__(self, writing: BlockWriting, output: PageOutput, section: PageSection) -> None:
        self._writing = writing
        self._output = output
        self._policy, self._file_page = section.policy, section.file_page
        self._held: list[tuple[Block, str]] = []
        self._withheld: list[WithheldNote] = []

    def hold(self, block: Block, html: str) -> None:
        self._held.append((block, html))

    def pass_over(self, block: Block, text: str) -> None:
        self.flush()
        if is_a_scope_piece(block):
            self._withhold_numbered([leading_note_number(text)])

    def withheld(self) -> list[WithheldNote]:
        return list(self._withheld)

    def flush(self) -> None:
        if not self._held:
            return
        blocks = [block for block, _html in self._held]
        if self._reads_as_prose(blocks):
            self._emit_prose(self._held)
        else:
            self._emit_list(blocks)
        self._held = []

    def _emit_prose(self, held: list[tuple[Block, str]]) -> None:
        converted = [element for block, html in held for element in self._writing.converted(block, html)]
        opened = self._one_paragraph_per_entry([block for block, _html in held], converted)
        self._output.emit(_continued_entries_joined(_opened_at_their_numbers(opened)))

    def _one_paragraph_per_entry(self, blocks: list[Block], elements: list) -> list:
        if not blocks:
            return elements
        entries = self._writing.hanging_entries(self._file_page, blocks)
        openings = LayerEntryOpenings([entry.text for entry in entries])
        return [entry for element in elements for entry in _entries_of(element, openings)]

    def _emit_list(self, blocks: list[Block]) -> None:
        unnumbered = self._unnumbered_blocks_above_the_first_number(blocks)
        self._emit_prose(self._held[:unnumbered])
        self._held = self._held[unnumbered:]
        self._emit_hanging_entries(blocks[unnumbered:])

    def _unnumbered_blocks_above_the_first_number(self, blocks: list[Block]) -> int:
        if self._output.is_empty() or not self._writing.is_numbered_list(self._file_page, blocks):
            return 0
        numbered = [leading_note_number(self._writing.text_of(html)) is not None for _block, html in self._held]
        return numbered.index(True) if any(numbered) else 0

    def _emit_hanging_entries(self, blocks: list[Block]) -> None:
        entries = self._writing.hanging_entries(self._file_page, blocks)
        kept = [entry for entry in entries if self._policy.keeps_box(self._file_page, entry.bbox)]
        self._withhold([entry for entry in entries if entry not in kept])
        paragraphs = self._writing.entry_paragraphs(self._file_page, kept, self._held)
        self._output.emit(self._carried_entry_resumed(blocks, paragraphs))

    def _carried_entry_resumed(self, blocks: list[Block], paragraphs: list) -> list:
        if not paragraphs or not self._carries_an_entry_over(blocks, paragraphs[0]):
            return paragraphs
        return [dataclasses.replace(paragraphs[0], resumes_mid_sentence=True)] + paragraphs[1:]

    def _carries_an_entry_over(self, blocks: list[Block], first: Paragraph) -> bool:
        opens_the_page = self._output.is_empty() and leading_note_number(first.text) is None
        return opens_the_page and self._writing.is_numbered_list(self._file_page, blocks)

    def _withhold(self, entries: list[ListEntry]) -> None:
        self._withhold_numbered([leading_note_number(entry.text) for entry in entries])

    def _withhold_numbered(self, numbers: list[str | None]) -> None:
        if self._policy.in_note_list:
            self._withheld += [WithheldNote(self._file_page, number, True) for number in numbers if number]

    def _reads_as_prose(self, blocks: list[Block]) -> bool:
        unnumbered_notes = self._policy.in_note_list and not self._writing.is_numbered_list(self._file_page, blocks)
        return unnumbered_notes or not self._writing.trusts_the_layer(self._file_page)


def _entries_of(element, openings: LayerEntryOpenings) -> list:
    if not isinstance(element, Paragraph):
        return [element]
    texts = openings.entries(element.text)
    if len(texts) == 1:
        return [dataclasses.replace(element, text=texts[0])]
    first = dataclasses.replace(element, text=texts[0], continues=False)
    inner = [Paragraph(text, False, element.file_page) for text in texts[1:-1]]
    return [first, *inner, Paragraph(texts[-1], element.continues, element.file_page)]


def _opened_at_their_numbers(elements: list) -> list:
    return [dataclasses.replace(element, resumes=False) if _opens_an_entry(element) else element
            for element in elements]


def _opens_an_entry(element) -> bool:
    return isinstance(element, Paragraph) and leading_note_number(element.text) is not None


def _continued_entries_joined(elements: list) -> list:
    numbers_its_entries = any(_numbers_an_entry(element) for element in elements)
    joined: list = []
    for element in elements:
        if joined and numbers_its_entries and _continues(joined[-1], element):
            joined[-1] = dataclasses.replace(joined[-1], text=f"{joined[-1].text} {_entry_words(element)}")
        else:
            joined.append(element)
    return joined


def _continues(entry, element) -> bool:
    if _numbers_an_entry(element) or not isinstance(entry, (Paragraph, Verbatim)):
        return False
    after_a_numbered_paragraph = isinstance(entry, Paragraph) and _numbers_an_entry(entry)
    return _is_a_list_item(element) or (isinstance(element, Paragraph) and after_a_numbered_paragraph)


def _is_a_list_item(element) -> bool:
    return isinstance(element, Verbatim) and element.text.startswith(LIST_ITEM_BULLET)


def _numbers_an_entry(element) -> bool:
    return isinstance(element, (Paragraph, Verbatim)) and leading_note_number(_entry_words(element)) is not None


def _entry_words(element) -> str:
    return element.text.removeprefix(LIST_ITEM_BULLET)
