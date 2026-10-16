from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import FOOTNOTE_KIND, HEADING_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.outline import Outline
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs
from _extract.writer import NoteWriter

FONT = "helv"
TITLE_SIZE = 16.0
BODY_SIZE = 10.0
NOTE_SIZE = 8.0
MARK_SIZE = 7.0
MARK_RISE = 7.0
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
LINE_HALF_HEIGHT = 10.0
TITLE_BASELINE = 90.0
BODY_BASELINE = 140.0
NOTE_BASELINE = 580.0
TITLE = "Hegel's Phenomenology"
SENTENCE = "The chapter opens with a sentence."
NOTE = "This chapter draws on an earlier paper."


class MarkedTitlePagePdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            page.insert_text((LEFT, TITLE_BASELINE), TITLE, fontsize=TITLE_SIZE, fontname=FONT)
            mark_left = LEFT + pymupdf.get_text_length(TITLE, FONT, TITLE_SIZE)
            page.insert_text((mark_left, TITLE_BASELINE - MARK_RISE), "1", fontsize=MARK_SIZE, fontname=FONT)
            page.insert_text((LEFT, BODY_BASELINE), SENTENCE, fontsize=BODY_SIZE, fontname=FONT)
            page.insert_text((LEFT, NOTE_BASELINE), f"1 {NOTE}", fontsize=NOTE_SIZE, fontname=FONT)
            document.set_toc([[1, TITLE, 1]])
            document.save(self._path)
        return self._path


def engine_block(kind: str, html: str, baseline: float) -> Block:
    box = (LEFT, baseline - LINE_HALF_HEIGHT - MARK_RISE, RIGHT, baseline + LINE_HALF_HEIGHT / 2)
    return Block(1, kind, html, box, {}, f"/page/1/{kind}/{baseline}")


def engine_reading() -> DocumentBlocks:
    return DocumentBlocks([PageBlocks(1, [engine_block(HEADING_KIND, f"<h1>{TITLE}<sup>1</sup></h1>", TITLE_BASELINE),
                                          engine_block(TEXT_KIND, f"<p>{SENTENCE}</p>", BODY_BASELINE),
                                          engine_block(FOOTNOTE_KIND, f"<p>1 {NOTE}</p>", NOTE_BASELINE)])])


class TestNoteMarksRaisedOnAHeadingTheOutlineNames(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        pdf_path = MarkedTitlePagePdf(Path(directory.name) / "page.pdf").write()
        layer = TextLayer(pdf_path)
        self.addCleanup(layer.close)
        inputs = StructureInputs(engine_reading(), Outline(pdf_path).headings(), WorkerReadings.none(),
                                 keep_everything())
        self.structure = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)

    def test_the_heading_keeps_the_notes_label(self) -> None:
        text = NoteWriter().render(self.structure.elements(), self.structure.definitions()).text
        self.assertIn(f"# {TITLE}\n\n[^1]\n", text)

    def test_the_note_the_heading_marks_stays_a_definition(self) -> None:
        self.assertEqual([(1, NOTE)],
                         [(definition.label, definition.text) for definition in self.structure.definitions()])


if __name__ == "__main__":
    unittest.main()
