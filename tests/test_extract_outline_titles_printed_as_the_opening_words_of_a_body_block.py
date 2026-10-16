from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import keep_everything, page_assembler
from _extract.blocks import TEXT_KIND, Block, PageBlocks
from _extract.layer import TextLayer
from _extract.outline import Heading as OutlineHeading
from _extract.structure import Heading

SECTION_LEVEL = 1
SUBLEVEL = 2
CARRIED_PROSE = "and so the argument of the section before comes to its close."
NUMERAL_TITLE = "II"
SMALL_CAPS_NUMERAL = "ii"
OPENING_PROSE = "But are these two turns in hermeneutics progress, or merely change?"
RUN_IN_TITLE = "2.1.1. The Structure of the Paradox"
RUN_IN_PROSE = f"{RUN_IN_TITLE} The mistake of demanding simple truth lies at the origin of the perplexity."
PROSE_PAST_THE_RUN_IN_TITLE = "The mistake of demanding simple truth lies at the origin of the perplexity."
PRONOUN_TITLE = "I"
PRONOUN_PROSE = "I think the argument of this section needs no numeral to open it."
RUN_IN_DESTINATION = 90.0
LEFT = 72.0
BODY_SIZE = 10.0
ROW_PITCH = 40.0
FIRST_BASELINE = 60.0
ROW_HEIGHT = 12.0
RIGHT = 540.0


class PrintedRows:
    def __init__(self, directory: Path, texts: list[str]) -> None:
        self._path = directory / "rows.pdf"
        self._texts = texts

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            for index, text in enumerate(self._texts):
                page.insert_text((LEFT, _baseline(index)), text, fontsize=BODY_SIZE)
            document.save(self._path)
        return self._path

    @property
    def blocks(self) -> PageBlocks:
        return PageBlocks(1, [Block(1, TEXT_KIND, f"<p>{text}</p>", _box(index), {}, f"/page/1/{index}")
                              for index, text in enumerate(self._texts)])


def _baseline(index: int) -> float:
    return FIRST_BASELINE + index * ROW_PITCH


def _box(index: int) -> tuple:
    baseline = _baseline(index)
    return (LEFT - 2.0, baseline - ROW_HEIGHT, RIGHT, baseline + 4.0)


class TestOutlineTitlesPrintedAsTheOpeningWordsOfABodyBlock(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def _texts(self, texts: list[str], due: OutlineHeading) -> list[str]:
        printed = PrintedRows(self._directory, texts)
        layer = TextLayer(printed.write())
        self.addCleanup(layer.close)
        assembler = page_assembler(layer, keep_everything())
        elements = assembler.assemble(printed.blocks, [due], SUBLEVEL).elements[1:]
        return [element.title if isinstance(element, Heading) else element.text for element in elements]

    def test_a_numeral_the_text_layer_sets_in_small_capitals_opens_its_heading_where_it_prints(self) -> None:
        texts = self._texts([CARRIED_PROSE, SMALL_CAPS_NUMERAL, OPENING_PROSE],
                            OutlineHeading(SECTION_LEVEL, NUMERAL_TITLE, 1))
        self.assertEqual([CARRIED_PROSE, NUMERAL_TITLE, OPENING_PROSE], texts)

    def test_a_title_run_into_its_paragraph_below_the_entrys_destination_leaves_the_paragraph(self) -> None:
        texts = self._texts([CARRIED_PROSE, RUN_IN_PROSE],
                            OutlineHeading(SUBLEVEL, RUN_IN_TITLE, 1, RUN_IN_DESTINATION))
        self.assertEqual([CARRIED_PROSE, RUN_IN_TITLE, PROSE_PAST_THE_RUN_IN_TITLE], texts)

    def test_a_one_word_title_a_paragraph_opens_with_as_a_word_of_its_prose_stays_in_the_paragraph(self) -> None:
        texts = self._texts([CARRIED_PROSE, PRONOUN_PROSE], OutlineHeading(SECTION_LEVEL, PRONOUN_TITLE, 1))
        self.assertEqual([CARRIED_PROSE, PRONOUN_TITLE, PRONOUN_PROSE], texts)


if __name__ == "__main__":
    unittest.main()
