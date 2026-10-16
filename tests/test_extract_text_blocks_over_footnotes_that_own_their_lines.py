from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.blocks import FOOTNOTE_KIND, TEXT_KIND, Block, PageBlocks
from _extract.layer import TextLayer
from _extract.structure import Paragraph
from _extract_fixtures import PrintedWork, keep_everything, page_assembler

FONT_SIZE = 9.0
LEFT = 40.0
HANGING_LEFT = 46.0
LINES = [("1 First note opens", LEFT, 100.0), ("and runs on.", HANGING_LEFT, 111.0), ("2 Second note.", LEFT, 122.0)]
FIRST_NOTE_BOX = (38.0, 90.0, 300.0, 114.0)
SECOND_NOTE_BOX = (38.0, 115.0, 300.0, 125.0)
LIST_BOX = (38.0, 91.0, 300.0, 124.0)
OWN_LINE_BOX = (38.0, 89.0, 300.0, 124.0)
LIST_ENGINE_HTML = "<p>and runs on. <sup>2</sup> Second note.</p>"


class HangingNotesPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            for text, left, baseline in LINES:
                page.insert_text((left, baseline), text, fontname="helv", fontsize=FONT_SIZE)
            document.save(self._path)
        return self._path


def footnote(html: str, box: tuple, index: int) -> Block:
    return Block(1, FOOTNOTE_KIND, html, box, {}, f"/page/1/Footnote/{index}")


def text_block(box: tuple) -> Block:
    return Block(1, TEXT_KIND, LIST_ENGINE_HTML, box, {}, "/page/1/Text/0")


class TestTextBlockOverFootnotesThatOwnItsLines(unittest.TestCase):
    def test_each_note_is_written_once_when_a_text_block_rereads_the_footnotes_inside_it(self) -> None:
        texts = self._written([text_block(LIST_BOX),
                               footnote("<p><sup>1</sup> First note opens</p>", FIRST_NOTE_BOX, 1),
                               footnote("<p></p>", SECOND_NOTE_BOX, 2)])
        self.assertEqual(["1. First note opens and runs on.", "2. Second note."], texts)

    def test_a_text_block_holding_a_line_of_its_own_beside_a_footnote_is_kept(self) -> None:
        texts = self._written([text_block(OWN_LINE_BOX), footnote("<p></p>", SECOND_NOTE_BOX, 2)])
        self.assertEqual(["1 First note opens and runs on.", "2. Second note."], texts)

    def test_a_page_read_from_pixels_keeps_the_text_block_whose_engine_text_is_the_only_copy(self) -> None:
        texts = self._written([text_block(LIST_BOX),
                               footnote("<p><sup>1</sup> First note opens</p>", FIRST_NOTE_BOX, 1),
                               footnote("<p></p>", SECOND_NOTE_BOX, 2)], pixel_pages=frozenset({1}))
        self.assertTrue(any("Second note." in text for text in texts))

    def _written(self, blocks: list[Block], pixel_pages: frozenset[int] = frozenset()) -> list[str]:
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory, True)
        layer = TextLayer(HangingNotesPdf(directory / "notes.pdf").write())
        self.addCleanup(layer.close)
        assembler = page_assembler(layer, keep_everything(), PrintedWork(pixel_pages=pixel_pages))
        result = assembler.assemble(PageBlocks(1, blocks), [], None)
        paragraphs = [element.text for element in result.elements if isinstance(element, Paragraph)]
        return paragraphs + [definition.text for definition in result.definitions]


if __name__ == "__main__":
    unittest.main()
