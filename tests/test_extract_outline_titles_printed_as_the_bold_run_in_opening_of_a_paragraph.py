from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeLayer, keep_everything, page_assembler
from _extract.blocks import Block, PageBlocks
from _extract.outline import Outline
from _extract.structure import Heading

PAGE_WIDTH = 439.0
PAGE_HEIGHT = 666.0
SECTION_LEVEL = 1
SECTION_TITLE = "1.1. Compositional structure"
NOTATION_TITLE = "2.1. The [0,1]-valued metric spaces"
CLOSING_PROSE = "The section before closes with this paragraph, above the paragraph the next section opens."
PROSE_PAST_THE_TITLE = "Expressions combine to make longer expressions, and their meanings combine with them."
BOLD_TITLE_CLOSED_BY_A_FULL_STOP = f"<p><b>{SECTION_TITLE}.</b> {PROSE_PAST_THE_TITLE}</p>"
BOLD_TITLE_CLOSED_BY_A_COLON = f"<p><b>{SECTION_TITLE}:</b> {PROSE_PAST_THE_TITLE}</p>"
TITLE_CLOSED_BY_A_FULL_STOP_OUTSIDE_THE_BOLD = f"<p><b>{SECTION_TITLE}</b>. {PROSE_PAST_THE_TITLE}</p>"
BOLD_TITLE_SPELLING_ITS_NOTATION_AS_A_FORMULA = (
    f"<p><b>2.1. The $[0, 1]$-valued metric spaces.</b> {PROSE_PAST_THE_TITLE}</p>")
CLOSING_TOP, CLOSING_BOTTOM = 250.0, 320.0
RUN_IN_TOP, RUN_IN_BOTTOM = 333.0, 370.0
DESTINATION_ABOVE_THE_CLOSING_PROSE = 200.0


class OutlinedPdf:
    def __init__(self, directory: str) -> None:
        self._path = Path(directory) / "outlined.pdf"

    def with_entry(self, title: str) -> Path:
        with pymupdf.open() as document:
            document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            destination = {"kind": 1, "to": pymupdf.Point(0, DESTINATION_ABOVE_THE_CLOSING_PROSE)}
            document.set_toc([[SECTION_LEVEL, title, 1, destination]])
            document.save(self._path)
        return self._path


def html_block(html: str, top: float, bottom: float) -> Block:
    return Block(1, "Text", html, (40.0, top, 400.0, bottom), {}, f"/page/1/Text/{top}")


class TestOutlineTitlesPrintedAsTheBoldRunInOpeningOfAParagraph(unittest.TestCase):
    def _texts(self, run_in_html: str, title: str = SECTION_TITLE) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            due = Outline(OutlinedPdf(directory).with_entry(title)).headings()
        blocks = [html_block(f"<p>{CLOSING_PROSE}</p>", CLOSING_TOP, CLOSING_BOTTOM),
                  html_block(run_in_html, RUN_IN_TOP, RUN_IN_BOTTOM)]
        assembler = page_assembler(FakeLayer(), keep_everything())
        elements = assembler.assemble(PageBlocks(1, blocks), due, SECTION_LEVEL + 1).elements[1:]
        return [element.title if isinstance(element, Heading) else element.text for element in elements]

    def test_a_bold_title_closed_by_a_full_stop_opens_its_heading_once_where_it_prints(self) -> None:
        self.assertEqual([CLOSING_PROSE, SECTION_TITLE, PROSE_PAST_THE_TITLE],
                         self._texts(BOLD_TITLE_CLOSED_BY_A_FULL_STOP))

    def test_a_bold_title_closed_by_a_colon_opens_its_heading_once_where_it_prints(self) -> None:
        self.assertEqual([CLOSING_PROSE, SECTION_TITLE, PROSE_PAST_THE_TITLE],
                         self._texts(BOLD_TITLE_CLOSED_BY_A_COLON))

    def test_a_full_stop_set_past_the_bold_title_leaves_the_paragraph_with_the_heading(self) -> None:
        self.assertEqual([CLOSING_PROSE, SECTION_TITLE, PROSE_PAST_THE_TITLE],
                         self._texts(TITLE_CLOSED_BY_A_FULL_STOP_OUTSIDE_THE_BOLD))

    def test_a_bold_title_spelling_the_outlines_notation_as_a_formula_opens_its_heading_once_where_it_prints(
            self) -> None:
        self.assertEqual([CLOSING_PROSE, NOTATION_TITLE, PROSE_PAST_THE_TITLE],
                         self._texts(BOLD_TITLE_SPELLING_ITS_NOTATION_AS_A_FORMULA, NOTATION_TITLE))


if __name__ == "__main__":
    unittest.main()
