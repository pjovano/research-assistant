from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import PrintedWork, keep_everything, page_assembler
from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, PageBlocks
from _extract.layer import TextLayer
from _extract.outline import Heading as OutlineHeading
from _extract.structure import Heading

WORK_TITLE = "Heidegger on Kant on Transcendence"
LABELLED_WORK_TITLE = "chapter 3: heidegger on kant on transcendence"
OPENED_SECTION = "3 Incompatibility Semantics"
PRINTED_APPENDIX = "Appendix I: Incompatibility Semantics"
OUTLINED_APPENDIX = "Appendix 1: Incompatibility Semantics"
PART_HEADING = "Technical Appendices"
PROSE = "The notes to this chapter follow the order of the marks the chapter raises in its text."
SECTION_LEVEL = 2
SUBLEVEL = 3
BODY_FONT = "helv"
HEADING_FONT = "tiro"
SMALL_CAPITALS_NAME = "/Bembo-SC"
BASE_FONT_KEY = "BaseFont"
LEFT = 72.0
HEADING_SIZE = 12.0
BODY_SIZE = 10.0
FIRST_BASELINE = 100.0
SECOND_BASELINE = 130.0
PROSE_BASELINE = 160.0
FIRST_BOX = (70.0, 86.0, 400.0, 104.0)
SECOND_BOX = (70.0, 116.0, 400.0, 134.0)
PROSE_BOX = (70.0, 150.0, 540.0, 164.0)


class HeadedPagesPdf:
    def __init__(self, directory: Path) -> None:
        self._path = directory / "headed.pdf"

    def write(self, pages: list[list[str]]) -> Path:
        with pymupdf.open() as document:
            for headings in pages:
                self._add_page(document, headings)
            document.save(self._path)
        return self._path

    @staticmethod
    def _add_page(document, headings: list[str]) -> None:
        page = document.new_page()
        for heading, baseline in zip(headings, (FIRST_BASELINE, SECOND_BASELINE)):
            page.insert_text((LEFT, baseline), heading, fontsize=HEADING_SIZE, fontname=HEADING_FONT)
        page.insert_text((LEFT, PROSE_BASELINE), PROSE, fontsize=BODY_SIZE, fontname=BODY_FONT)
        heading_font = next(font[0] for font in page.get_fonts() if font[4] == HEADING_FONT)
        document.xref_set_key(heading_font, BASE_FONT_KEY, SMALL_CAPITALS_NAME)


def headed_page(file_page: int, headings: list[str]) -> PageBlocks:
    blocks = [Block(file_page, HEADING_KIND, f"<h2>{heading}</h2>", box, {}, f"/page/{file_page}/{index}")
              for index, (heading, box) in enumerate(zip(headings, (FIRST_BOX, SECOND_BOX)))]
    return PageBlocks(file_page, blocks + [Block(file_page, TEXT_KIND, f"<p>{PROSE}</p>", PROSE_BOX, {},
                                                 f"/page/{file_page}/prose")])


class TestHeadingsPrintingALabelBeforeATitleARunningHeadNames(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def _assembler(self, pages: list[list[str]]):
        layer = TextLayer(HeadedPagesPdf(self._directory).write(pages))
        self.addCleanup(layer.close)
        return page_assembler(layer, keep_everything(), PrintedWork(work_title=WORK_TITLE))

    @staticmethod
    def _titles(elements: list) -> list[str]:
        return [element.title for element in elements if isinstance(element, Heading)]

    def test_a_label_before_the_works_title_opens_a_section_of_its_own(self) -> None:
        assembler = self._assembler([[LABELLED_WORK_TITLE]])
        elements = assembler.assemble(headed_page(1, [LABELLED_WORK_TITLE]), [], SUBLEVEL).elements
        self.assertEqual([LABELLED_WORK_TITLE], self._titles(elements))

    def test_a_label_before_an_opened_sections_title_opens_its_outline_entry_where_it_prints(self) -> None:
        assembler = self._assembler([[OPENED_SECTION], [PART_HEADING, PRINTED_APPENDIX]])
        assembler.assemble(headed_page(1, [OPENED_SECTION]), [OutlineHeading(SECTION_LEVEL, OPENED_SECTION, 1)],
                           SUBLEVEL)
        due = [OutlineHeading(SECTION_LEVEL, OUTLINED_APPENDIX, 2)]
        elements = assembler.assemble(headed_page(2, [PART_HEADING, PRINTED_APPENDIX]), due, SUBLEVEL).elements
        self.assertEqual([PART_HEADING, OUTLINED_APPENDIX], self._titles(elements))

    def test_the_works_title_printed_bare_is_still_dropped_as_its_running_head(self) -> None:
        assembler = self._assembler([[WORK_TITLE]])
        elements = assembler.assemble(headed_page(1, [WORK_TITLE]), [], SUBLEVEL).elements
        self.assertEqual([], self._titles(elements))


if __name__ == "__main__":
    unittest.main()
