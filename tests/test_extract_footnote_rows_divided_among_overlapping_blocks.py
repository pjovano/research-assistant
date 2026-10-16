from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import FOOTNOTE_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs
from _extract.writer import NoteWriter

FONT = "helv"
BODY_SIZE = 10.0
NOTE_SIZE = 8.0
MARK_SIZE = 6.0
MARK_RISE = 4.0
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
LINE_ASCENT = 8.0
LINE_DESCENT = 4.0
FILE_PAGE = 1
BODY_LINES = ((100.0, "Logic is said to abstract from all content.", "1"),
              (140.0, "The later lectures press the same point.", "2"),
              (180.0, "Others read the doctrine as a phenomenology.", "3"))
FIRST_NOTE = "Kant, Logik, AA IX, 13."
SECOND_NOTE_OPENING = "Fuchs, Der Grundansatz der ersten Wissenschaftslehre Jo-"
SECOND_NOTE_TAIL = "hann Gottlieb Fichtes, p. 115."
SECOND_NOTE = "Fuchs, Der Grundansatz der ersten Wissenschaftslehre Johann Gottlieb Fichtes, p. 115."
THIRD_NOTE = "Janke, Vom Bilde des Absolutes, p. 187."
NOTE_LINES = ((480.0, f"1 {FIRST_NOTE}"), (492.0, f"2 {SECOND_NOTE_OPENING}"), (504.0, SECOND_NOTE_TAIL),
              (516.0, f"3 {THIRD_NOTE}"))
INNER_BLOCK_BASELINE = 492.0
DEFINITION_RE = re.compile(r"^\[\^(\d+)\]: (.*)$", re.MULTILINE)


class OverlappingNoteBlocksPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            for baseline, sentence, mark in BODY_LINES:
                page.insert_text((LEFT, baseline), sentence, fontsize=BODY_SIZE, fontname=FONT)
                mark_left = LEFT + pymupdf.get_text_length(sentence, FONT, BODY_SIZE)
                page.insert_text((mark_left, baseline - MARK_RISE), mark, fontsize=MARK_SIZE, fontname=FONT)
            for baseline, text in NOTE_LINES:
                page.insert_text((LEFT, baseline), text, fontsize=NOTE_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


def engine_reading() -> list[PageBlocks]:
    body = [Block(FILE_PAGE, TEXT_KIND, f"<p>{sentence}<sup>{mark}</sup></p>", _box(baseline, baseline), {},
                  f"/page/0/Text/{index}") for index, (baseline, sentence, mark) in enumerate(BODY_LINES)]
    covering = Block(FILE_PAGE, TEXT_KIND, "<p>" + " ".join(text for _baseline, text in NOTE_LINES) + "</p>",
                     _box(NOTE_LINES[0][0], NOTE_LINES[-1][0]), {}, "/page/0/Text/covering")
    inner = Block(FILE_PAGE, FOOTNOTE_KIND, "", _box(INNER_BLOCK_BASELINE, INNER_BLOCK_BASELINE), {},
                  "/page/0/Footnote/inner")
    return [PageBlocks(FILE_PAGE, body + [covering, inner])]


def _box(first_baseline: float, last_baseline: float) -> tuple[float, float, float, float]:
    return (LEFT, first_baseline - LINE_ASCENT, RIGHT, last_baseline + LINE_DESCENT)


class TestFootnoteRowsDividedAmongOverlappingBlocks(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(OverlappingNoteBlocksPdf(Path(directory.name) / "notes.pdf").write())
        self.addCleanup(layer.close)
        inputs = StructureInputs(DocumentBlocks(engine_reading()), [], WorkerReadings.none(), keep_everything())
        structure = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)
        self.definitions = DEFINITION_RE.findall(NoteWriter().render(structure.elements(),
                                                                     structure.definitions()).text)

    def test_the_note_above_the_inner_block_keeps_only_its_own_text(self) -> None:
        self.assertIn(("1", FIRST_NOTE), self.definitions)

    def test_a_tail_line_the_covering_block_holds_stays_with_the_note_it_ends(self) -> None:
        self.assertIn(("2", SECOND_NOTE), self.definitions)

    def test_a_note_the_covering_block_holds_below_the_inner_block_is_a_note_of_its_own(self) -> None:
        self.assertIn(("3", THIRD_NOTE), self.definitions)

    def test_the_notes_keep_the_order_the_page_prints(self) -> None:
        self.assertEqual(["1", "2", "3"], [label for label, _text in self.definitions])


if __name__ == "__main__":
    unittest.main()
