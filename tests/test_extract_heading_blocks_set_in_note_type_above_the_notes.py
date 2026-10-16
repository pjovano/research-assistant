from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import keep_everything, page_assembler
from _extract.blocks import FOOTNOTE_KIND, HEADING_KIND, TEXT_KIND, Block, PageBlocks
from _extract.layer import TextLayer
from _extract.structure import Heading

LEFT = 72.0
BODY_SIZE = 10.0
NOTE_SIZE = 8.0
BODY_LINES = ("Bolzano holds that the pedagogical form is the only way left to him", "to make this point plain.")
BODY_MARK = "62"
FIRST_NOTE = f"{BODY_MARK}. BGA 1, 14/3, 652-653 / 258."
SECOND_NOTE = "63. For example, Ibid., 648 / 255."
BODY_BASELINES = (100.0, 114.0)
FIRST_NOTE_BASELINE = 400.0
SECOND_NOTE_BASELINE = 412.0
BODY_BOX = (70.0, 88.0, 540.0, 118.0)
FIRST_NOTE_BOX = (70.0, 392.0, 300.0, 403.0)
SECOND_NOTE_BOX = (70.0, 404.0, 300.0, 415.0)
MARKED_BODY = f"<p>{BODY_LINES[0]} {BODY_LINES[1]}<sup>{BODY_MARK}</sup></p>"


class NotedPagePdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self, first_note_size: float) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            for baseline, line in zip(BODY_BASELINES, BODY_LINES):
                page.insert_text((LEFT, baseline), line, fontsize=BODY_SIZE)
            page.insert_text((LEFT, FIRST_NOTE_BASELINE), FIRST_NOTE, fontsize=first_note_size)
            page.insert_text((LEFT, SECOND_NOTE_BASELINE), SECOND_NOTE, fontsize=NOTE_SIZE)
            document.save(self._path)
        return self._path


def engine_reading() -> PageBlocks:
    return PageBlocks(1, [Block(1, TEXT_KIND, MARKED_BODY, BODY_BOX, {}, "/page/1/0"),
                          Block(1, HEADING_KIND, f"<h2>{FIRST_NOTE}</h2>", FIRST_NOTE_BOX, {}, "/page/1/1"),
                          Block(1, FOOTNOTE_KIND, f"<p>{SECOND_NOTE}</p>", SECOND_NOTE_BOX, {}, "/page/1/2")])


class TestHeadingBlocksSetInNoteTypeAboveTheNotes(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def _assembled(self, first_note_size: float):
        layer = TextLayer(NotedPagePdf(self._directory / "noted.pdf").write(first_note_size))
        self.addCleanup(layer.close)
        assembler = page_assembler(layer, keep_everything())
        return assembler.assemble(engine_reading(), [], 2)

    def test_a_heading_block_set_in_note_type_above_the_notes_is_a_footnote_not_a_heading(self) -> None:
        result = self._assembled(NOTE_SIZE)
        self.assertEqual([], [element for element in result.elements if isinstance(element, Heading)])

    def test_a_heading_block_set_in_note_type_above_the_notes_defines_the_mark_it_names(self) -> None:
        result = self._assembled(NOTE_SIZE)
        self.assertIn(BODY_MARK, [definition.number for definition in result.definitions])

    def test_a_heading_block_set_in_body_type_above_the_notes_stays_a_heading(self) -> None:
        result = self._assembled(BODY_SIZE)
        self.assertEqual(1, len([element for element in result.elements if isinstance(element, Heading)]))


if __name__ == "__main__":
    unittest.main()
