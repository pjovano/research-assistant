from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import PrintedWork, keep_everything, page_assembler
from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, PageBlocks
from _extract.headings import LetterSpacedHeading
from _extract.layer import TextLayer
from _extract.structure import Heading

FONT = "cour"
LABEL_SIZE = 14.0
BODY_SIZE = 9.0
INVISIBLE = 3
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
FILE_PAGE = 1
ENGINE_LABEL = "C H A P T E R 1 4"
LAYER_LABEL = "c u a p r e r   I 4"
REJOINED_LABEL = "CHAPTER 14"
BODY = "The opening sentence of the chapter."
LABEL_BASELINE = 100.0
BODY_BASELINE = 200.0
LINE_HALF_HEIGHT = 10.0


class RecognizedScanPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            for baseline, text, size in [(LABEL_BASELINE, LAYER_LABEL, LABEL_SIZE), (BODY_BASELINE, BODY, BODY_SIZE)]:
                page.insert_text((LEFT, baseline), text, fontsize=size, fontname=FONT, render_mode=INVISIBLE)
            document.save(self._path)
        return self._path


def engine_block(kind: str, text: str, baseline: float) -> Block:
    box = (LEFT, baseline - LINE_HALF_HEIGHT, RIGHT, baseline + LINE_HALF_HEIGHT / 2)
    return Block(FILE_PAGE, kind, f"<p>{text}</p>", box, {}, f"/page/{FILE_PAGE}/{kind}/{baseline}")


class TestLetterSpacedHeadingsOnAPageWhoseTextLayerIsNotDrawn(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(RecognizedScanPdf(Path(directory.name) / "scan.pdf").write())
        self.addCleanup(layer.close)
        assembler = page_assembler(layer, keep_everything(), PrintedWork(pixel_pages=frozenset({FILE_PAGE})))
        blocks = [engine_block(HEADING_KIND, ENGINE_LABEL, LABEL_BASELINE), engine_block(TEXT_KIND, BODY, BODY_BASELINE)]
        self.result = assembler.assemble(PageBlocks(FILE_PAGE, blocks), [], 1)

    def test_the_heading_rejoins_the_engines_letters_not_the_text_layers(self) -> None:
        titles = [element.title for element in self.result.elements if isinstance(element, Heading)]
        self.assertEqual([REJOINED_LABEL], titles)


class TestLetterSpacedTextWithoutCharactersToMeasure(unittest.TestCase):
    def test_runs_of_single_letters_and_of_single_digits_are_rejoined_as_words_apart(self) -> None:
        self.assertEqual(REJOINED_LABEL, LetterSpacedHeading([]).rejoined(ENGINE_LABEL))

    def test_a_word_set_whole_after_the_spaced_letters_stays_a_word_of_its_own(self) -> None:
        self.assertEqual("CHAPTER 8 Time", LetterSpacedHeading([]).rejoined("C H A P T E R 8 Time"))


if __name__ == "__main__":
    unittest.main()
