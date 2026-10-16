from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import PrintedWork, keep_everything, page_assembler
from _extract.blocks import FOOTNOTE_KIND, HEADING_KIND, TEXT_KIND, Block, PageBlocks
from _extract.layer import TextLayer
from _extract.structure import Paragraph

FONT = "cour"
FONT_SIZE = 9.0
INVISIBLE = 3
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
FILE_PAGE = 1
BODY = "The closing sentence of the body."
NOTES_TITLE = "NOTES"
ENGINE_NOTES = ["1 See Anna Barnes's short essay.", "2 Lectures, ed. J. Moore, p. 21."]
LAYER_NOTES = ["1 See Anna Bames's short essay.", "2 Lectures, ed. 1. Moore, p. 21."]
BODY_BASELINE = 100.0
TITLE_BASELINE = 300.0
FIRST_NOTE_BASELINE = 330.0
NOTE_PITCH = 20.0
LINE_HALF_HEIGHT = 8.0


def baselines(notes: list[str]) -> list[tuple[float, str]]:
    return [(FIRST_NOTE_BASELINE + row * NOTE_PITCH, note) for row, note in enumerate(notes)]


class RecognizedScanPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            for baseline, text in [(BODY_BASELINE, BODY), (TITLE_BASELINE, NOTES_TITLE)] + baselines(LAYER_NOTES):
                page.insert_text((LEFT, baseline), text, fontsize=FONT_SIZE, fontname=FONT, render_mode=INVISIBLE)
            document.save(self._path)
        return self._path


def engine_block(kind: str, text: str, baseline: float) -> Block:
    box = (LEFT, baseline - LINE_HALF_HEIGHT, RIGHT, baseline + LINE_HALF_HEIGHT / 2)
    return Block(FILE_PAGE, kind, f"<p>{text}</p>", box, {}, f"/page/{FILE_PAGE}/{kind}/{baseline}")


def engine_reading() -> list[Block]:
    notes = [engine_block(FOOTNOTE_KIND, note, baseline) for baseline, note in baselines(ENGINE_NOTES)]
    return [engine_block(TEXT_KIND, BODY, BODY_BASELINE),
            engine_block(HEADING_KIND, NOTES_TITLE, TITLE_BASELINE)] + notes


class TestNotesListsOnAPageWhoseTextLayerIsNotDrawn(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(RecognizedScanPdf(Path(directory.name) / "scan.pdf").write())
        self.addCleanup(layer.close)
        assembler = page_assembler(layer, keep_everything(), PrintedWork(pixel_pages=frozenset({FILE_PAGE})))
        self.result = assembler.assemble(PageBlocks(FILE_PAGE, engine_reading()), [], 1)

    def test_the_entries_beneath_the_notes_heading_carry_the_engines_reading_not_the_text_layers(self) -> None:
        paragraphs = [element.text for element in self.result.elements if isinstance(element, Paragraph)]
        self.assertEqual([BODY] + ENGINE_NOTES, paragraphs)


if __name__ == "__main__":
    unittest.main()
