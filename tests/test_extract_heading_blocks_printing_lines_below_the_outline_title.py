from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import keep_everything, page_assembler
from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, PageBlocks
from _extract.layer import TextLayer
from _extract.outline import Heading as OutlineHeading
from _extract.structure import Heading

TITLE = "Modal formalism, a renunciation of thinking"
CITATION = "(GW 11, 381-385; S. 6, 202-207)"
RUN_ON = "and its Critics"
PROSE = "The first moment is that of formalism, in which the modal categories are defined by one another."
LEVEL = 3
SUBLEVEL = 4
FILE_PAGE = 1
LEFT = 72.0
HEADING_SIZE = 11.0
BODY_SIZE = 10.0
TITLE_BASELINE = 100.0
SECOND_LINE_BASELINE = 114.0
PROSE_BASELINE = 140.0
HEADING_BOX = (70.0, 88.0, 420.0, 118.0)
PROSE_BOX = (70.0, 130.0, 560.0, 144.0)


class HeadedPagePdf:
    def __init__(self, directory: Path) -> None:
        self._path = directory / "headed.pdf"

    def write(self, heading_lines: list[tuple[tuple[float, float], str]]) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            for (left, baseline), text in heading_lines:
                page.insert_text((left, baseline), text, fontsize=HEADING_SIZE)
            page.insert_text((LEFT, PROSE_BASELINE), PROSE, fontsize=BODY_SIZE)
            document.save(self._path)
        return self._path


def headed_page(heading: str) -> PageBlocks:
    return PageBlocks(FILE_PAGE, [Block(FILE_PAGE, HEADING_KIND, f"<h3>{heading}</h3>", HEADING_BOX, {}, "/page/1/0"),
                                  Block(FILE_PAGE, TEXT_KIND, f"<p>{PROSE}</p>", PROSE_BOX, {}, "/page/1/1")])


def _after_the_title() -> float:
    return LEFT + pymupdf.get_text_length(f"{TITLE} ", fontsize=HEADING_SIZE)


class TestHeadingBlocksPrintingLinesBelowTheOutlineTitle(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def _written(self, heading_lines: list[tuple[tuple[float, float], str]]) -> list[str]:
        layer = TextLayer(HeadedPagePdf(self._directory).write(heading_lines))
        self.addCleanup(layer.close)
        assembler = page_assembler(layer, keep_everything())
        printed = " ".join(text for _place, text in heading_lines)
        elements = assembler.assemble(headed_page(printed), [OutlineHeading(LEVEL, TITLE, FILE_PAGE)],
                                      SUBLEVEL).elements[1:]
        return [element.title if isinstance(element, Heading) else element.text for element in elements]

    def test_a_line_printed_below_the_outline_title_is_written_beneath_its_heading(self) -> None:
        lines = [((LEFT, TITLE_BASELINE), TITLE), ((LEFT, SECOND_LINE_BASELINE), CITATION)]
        self.assertEqual([TITLE, CITATION, PROSE], self._written(lines))

    def test_words_run_on_after_the_title_on_its_own_line_are_not_written_apart(self) -> None:
        lines = [((LEFT, TITLE_BASELINE), TITLE), ((_after_the_title(), TITLE_BASELINE), RUN_ON)]
        self.assertEqual([TITLE, PROSE], self._written(lines))


if __name__ == "__main__":
    unittest.main()
