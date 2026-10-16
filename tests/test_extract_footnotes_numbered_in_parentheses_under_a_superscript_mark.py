from __future__ import annotations

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
MARK_SIZE = 6.0
MARK_RISE = 4.0
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
BODY_BASELINE = 100.0
NOTE_BASELINE = 600.0
LINE_HALF_HEIGHT = 8.0
BEFORE_MARK = "Das Wirkliche, so Hegel"
MARK = "1"
AFTER_MARK = ", mit einem Begriff, der"
BODY_TAIL = "sich noch nicht bestimmen lässt."
NOTE = "(1) Vgl. Hegel, Wissenschaft der Logik, Bd. I, S. 12."
SUPERSCRIPT_ONE = "\u00b9"
RAISED_MARK_HTML = f"<p>{BEFORE_MARK}<sup>{MARK}</sup>{AFTER_MARK}</p>"
SUPERSCRIPT_CHARACTER_HTML = f"<p>{BEFORE_MARK}{SUPERSCRIPT_ONE}{AFTER_MARK}</p>"


class SuperscriptMarkedPagePdf:
    def __init__(self, path: Path, raises_the_mark: bool) -> None:
        self._path = path
        self._raises_the_mark = raises_the_mark

    def write(self) -> Path:
        with pymupdf.open() as document:
            first = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            write_the_body = self._marked_body if self._raises_the_mark else self._body_with_a_superscript_character
            write_the_body(first)
            first.insert_text((LEFT, NOTE_BASELINE), NOTE, fontsize=BODY_SIZE, fontname=FONT)
            second = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            second.insert_text((LEFT, BODY_BASELINE), BODY_TAIL, fontsize=BODY_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path

    @staticmethod
    def _marked_body(page) -> None:
        page.insert_text((LEFT, BODY_BASELINE), BEFORE_MARK, fontsize=BODY_SIZE, fontname=FONT)
        mark_left = LEFT + pymupdf.get_text_length(BEFORE_MARK, FONT, BODY_SIZE)
        page.insert_text((mark_left, BODY_BASELINE - MARK_RISE), MARK, fontsize=MARK_SIZE, fontname=FONT)
        after_left = mark_left + pymupdf.get_text_length(MARK, FONT, MARK_SIZE)
        page.insert_text((after_left, BODY_BASELINE), AFTER_MARK, fontsize=BODY_SIZE, fontname=FONT)

    @staticmethod
    def _body_with_a_superscript_character(page) -> None:
        text = f"{BEFORE_MARK}{SUPERSCRIPT_ONE}{AFTER_MARK}"
        page.insert_text((LEFT, BODY_BASELINE), text, fontsize=BODY_SIZE, fontname=FONT)


def engine_block(file_page: int, kind: str, html: str) -> Block:
    baseline = NOTE_BASELINE if kind == FOOTNOTE_KIND else BODY_BASELINE
    box = (LEFT, baseline - LINE_HALF_HEIGHT, RIGHT, baseline + LINE_HALF_HEIGHT / 2)
    continued = file_page == 1 and kind == TEXT_KIND
    return Block(file_page, kind, html, box, {}, f"/page/{file_page}/{kind}/{baseline}", continued)


def engine_reading(body_html: str) -> list[PageBlocks]:
    first = [engine_block(1, TEXT_KIND, body_html), engine_block(1, FOOTNOTE_KIND, f"<p>{NOTE}</p>")]
    return [PageBlocks(1, first), PageBlocks(2, [engine_block(2, TEXT_KIND, f"<p>{BODY_TAIL}</p>")])]


class TestFootnotesNumberedInParenthesesUnderASuperscriptMark(unittest.TestCase):
    RAISES_THE_MARK = True
    BODY_HTML = RAISED_MARK_HTML

    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(SuperscriptMarkedPagePdf(Path(directory.name) / "page.pdf", self.RAISES_THE_MARK).write())
        self.addCleanup(layer.close)
        reading = DocumentBlocks(engine_reading(self.BODY_HTML))
        inputs = StructureInputs(reading, [], WorkerReadings.none(), keep_everything())
        structure = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)
        self.text = NoteWriter().render(structure.elements(), structure.definitions()).text
        self.definitions = [definition.text for definition in structure.definitions()]

    def test_a_body_size_note_opening_with_a_parenthesised_number_under_a_superscript_mark_is_a_definition(
            self) -> None:
        self.assertEqual([NOTE], self.definitions)

    def test_the_body_sentence_above_it_stays_whole_across_the_page_marker(self) -> None:
        self.assertIn(f"%% file p. 2 %% {BODY_TAIL}", self.text.split("# Notes")[0])
        self.assertNotIn(NOTE, self.text.split("# Notes")[0])


class TestFootnotesNumberedInParenthesesUnderASuperscriptCharacter(
        TestFootnotesNumberedInParenthesesUnderASuperscriptMark):
    RAISES_THE_MARK = False
    BODY_HTML = SUPERSCRIPT_CHARACTER_HTML


if __name__ == "__main__":
    unittest.main()
