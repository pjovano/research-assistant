from __future__ import annotations

from _extract.blocks import FOOTER_KIND, FOOTNOTE_KIND, Block
from _extract.candidates import RunningHeads
from _extract.footnotes import leading_note_number
from _extract.layerlines import PageLines, box_of_rows, paragraph_of_rows, row_text

_NOTE_SUFFIX_TEMPLATE = "/note-{index}"


class FooterNotes:
    def __init__(self, running_heads: RunningHeads, lines: PageLines, body_marks: set[str]) -> None:
        self._running_heads = running_heads
        self._lines = lines
        self._body_marks = body_marks

    def refiled(self, blocks: list[Block]) -> list[Block]:
        return [piece for block in blocks for piece in self._pieces(block)]

    def _pieces(self, block: Block) -> list[Block]:
        rows = self._lines.of(block)
        if not self._holds_a_marked_note(block, rows):
            return [block]
        return [_note_block(block, index, note_rows) for index, note_rows in enumerate(self._notes_of(rows))]

    def _holds_a_marked_note(self, block: Block, rows: list[list]) -> bool:
        is_a_running_foot = self._running_heads.repeats_past_its_opening_numeral(block.plain_text)
        is_a_note_footer = block.kind == FOOTER_KIND and not is_a_running_foot
        return is_a_note_footer and any(self._opens_a_marked_note(row) for row in rows)

    def _notes_of(self, rows: list[list]) -> list[list[list]]:
        notes: list[list[list]] = []
        for row in rows:
            if notes and not self._opens_a_marked_note(row):
                notes[-1].append(row)
            else:
                notes.append([row])
        return notes

    def _opens_a_marked_note(self, row: list) -> bool:
        return leading_note_number(row_text(row)) in self._body_marks


def _note_block(footer: Block, index: int, rows: list[list]) -> Block:
    identifier = footer.identifier + _NOTE_SUFFIX_TEMPLATE.format(index=index)
    return Block(footer.file_page, FOOTNOTE_KIND, paragraph_of_rows(rows), box_of_rows(rows), {}, identifier)
