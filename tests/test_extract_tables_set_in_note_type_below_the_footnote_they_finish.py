from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import NamedTuple

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import FOOTNOTE_KIND, TABLE_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.elements import Paragraph, Verbatim
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

FONT = "helv"
FILE_PAGE = 1
BODY_SIZE = 10.0
NOTE_SIZE = 8.0
MARK_SIZE = 6.0
MARK_RISE = 4.0
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
STEP_LEFT = 80.0
REASON_LEFT = 200.0
RIGHT = 360.0
LINE_HALF_HEIGHT = 6.0
BODY_BASELINE = 100.0
NOTE_BASELINE = 520.0
FIRST_ROW_BASELINE = 540.0
ROW_PITCH = 12.0
SENTENCE = "Mott shows that the principle lets us believe anything at all."
MARK = "7"
NOTE = "See Mott. Here is a brief statement of his argument:"
ROWS = (("1. p implies q", "premise"), ("2. p", "assumption"), ("3. q", "from 1 and 2"))
BODY_KINDS = (Paragraph, Verbatim)
ROWS_AS_TEXT = " ".join(f"{step} {reason}" for step, reason in ROWS)


class TableRows(NamedTuple):
    size: float

    def draw_on(self, page) -> None:
        for index, (step, reason) in enumerate(ROWS):
            baseline = FIRST_ROW_BASELINE + index * ROW_PITCH
            page.insert_text((STEP_LEFT, baseline), step, fontsize=self.size, fontname=FONT)
            page.insert_text((REASON_LEFT, baseline), reason, fontsize=self.size, fontname=FONT)

    def block(self) -> Block:
        last_baseline = FIRST_ROW_BASELINE + (len(ROWS) - 1) * ROW_PITCH
        box = (STEP_LEFT, FIRST_ROW_BASELINE - LINE_HALF_HEIGHT * 2, RIGHT, last_baseline + LINE_HALF_HEIGHT)
        cells = "".join(f"<tr><td>{step}</td><td>{reason}</td></tr>\n" for step, reason in ROWS)
        return Block(FILE_PAGE, TABLE_KIND, f"<table><tbody>\n{cells}</tbody></table>", box, {}, "/page/1/Table/0")


def written_pdf(path: Path, rows: TableRows) -> Path:
    with pymupdf.open() as document:
        page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        page.insert_text((LEFT, BODY_BASELINE), SENTENCE, fontsize=BODY_SIZE, fontname=FONT)
        mark_left = LEFT + pymupdf.get_text_length(SENTENCE, FONT, BODY_SIZE)
        page.insert_text((mark_left, BODY_BASELINE - MARK_RISE), MARK, fontsize=MARK_SIZE, fontname=FONT)
        page.insert_text((LEFT, NOTE_BASELINE), f"{MARK} {NOTE}", fontsize=NOTE_SIZE, fontname=FONT)
        rows.draw_on(page)
        document.save(path)
    return path


def line_block(kind: str, html: str, baseline: float) -> Block:
    box = (LEFT, baseline - LINE_HALF_HEIGHT * 2, RIGHT, baseline + LINE_HALF_HEIGHT)
    return Block(FILE_PAGE, kind, html, box, {}, f"/page/{FILE_PAGE}/{kind}/{baseline}")


def engine_reading(rows: TableRows) -> list[PageBlocks]:
    return [PageBlocks(FILE_PAGE, [line_block(TEXT_KIND, f"<p>{SENTENCE}<sup>{MARK}</sup></p>", BODY_BASELINE),
                                   line_block(FOOTNOTE_KIND, f"<p><sup>{MARK}</sup> {NOTE}</p>", NOTE_BASELINE),
                                   rows.block()])]


class TestTablesSetInNoteTypeBelowTheFootnoteTheyFinish(unittest.TestCase):
    def built(self, rows: TableRows) -> NoteStructure:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(written_pdf(Path(directory.name) / "table.pdf", rows))
        self.addCleanup(layer.close)
        inputs = StructureInputs(DocumentBlocks(engine_reading(rows)), [], WorkerReadings.none(), keep_everything())
        return NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)

    def test_a_note_type_table_below_a_footnote_joins_the_footnote_as_one_line(self) -> None:
        definitions = self.built(TableRows(NOTE_SIZE)).definitions()
        self.assertEqual([f"{NOTE} {ROWS_AS_TEXT}"], [definition.text for definition in definitions])

    def test_a_note_type_table_below_a_footnote_leaves_the_body(self) -> None:
        elements = self.built(TableRows(NOTE_SIZE)).elements()
        self.assertEqual([f"{SENTENCE}[^7]"], [element.text for element in elements if isinstance(element, BODY_KINDS)])

    def test_a_body_type_table_below_a_footnote_stays_out_of_the_footnote(self) -> None:
        definitions = self.built(TableRows(BODY_SIZE)).definitions()
        self.assertEqual([NOTE], [definition.text for definition in definitions])


if __name__ == "__main__":
    unittest.main()
