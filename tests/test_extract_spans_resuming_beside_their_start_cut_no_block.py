from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import page_assembler
from _extract.blocks import TEXT_KIND, Block, PageBlocks
from _extract.layer import TextLayer
from _extract.policy import SectionPolicy
from _extract.spans import ScopePoints
from _extract.structure import Paragraph

FILE_PAGE = 1
SUBLEVEL = 2
FONT_SIZE = 9.0
LINE_PITCH = 15.0
FIRST_BASELINE = 120.0
SIDEBAR_X, ABSTRACT_X = 40.0, 200.0
SIDEBAR_RIGHT, ABSTRACT_RIGHT = 180.0, 440.0
ABSTRACT_OFFSET = 4.0
PAGE_WIDTH, PAGE_HEIGHT = 480.0, 680.0
SIDEBAR_LINES = ["Department of Philosophy,", "University of Somewhere,", "Street 1, Room 2,", "Some Country."]
ABSTRACT_LINES = ["The abstract opens beside the department and", "runs on beside the university, then on",
                  "beside the street, and closes on this", "line, beside the country."]


class SidebarBesideAbstractPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            for row, (sidebar, abstract) in enumerate(zip(SIDEBAR_LINES, ABSTRACT_LINES)):
                baseline = FIRST_BASELINE + row * LINE_PITCH
                page.insert_text((SIDEBAR_X, baseline), sidebar, fontsize=FONT_SIZE)
                page.insert_text((ABSTRACT_X, baseline + ABSTRACT_OFFSET), abstract, fontsize=FONT_SIZE)
            document.save(self._path)
        return self._path


def spans_from_each_sidebar_line_to_the_abstract_line_set_just_below_beside_it() -> list[tuple[str, str]]:
    return [(f"{FILE_PAGE}: {SIDEBAR_LINES[row]}", f"{FILE_PAGE}: {ABSTRACT_LINES[row]}")
            for row in range(len(SIDEBAR_LINES) - 1)]


def column_block(layer: TextLayer, lines: list[str], right: float, index: int) -> Block:
    boxes = [line.box for line in layer.lines(FILE_PAGE) if line.text.strip() in lines]
    box = (boxes[0].left, boxes[0].top, right, boxes[-1].bottom)
    return Block(FILE_PAGE, TEXT_KIND, f"<p>{' '.join(lines)}</p>", box, {}, f"/page/{FILE_PAGE}/Text/{index}")


class TestSpansResumingBesideTheirStartCutNoBlock(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.layer = TextLayer(SidebarBesideAbstractPdf(Path(directory.name) / "front.pdf").write())
        self.addCleanup(self.layer.close)

    def paragraphs(self) -> list[str]:
        policy = SectionPolicy(ScopePoints(self.layer).spans(
            spans_from_each_sidebar_line_to_the_abstract_line_set_just_below_beside_it()))
        page = PageBlocks(FILE_PAGE, [column_block(self.layer, SIDEBAR_LINES, SIDEBAR_RIGHT, 0),
                                      column_block(self.layer, ABSTRACT_LINES, ABSTRACT_RIGHT, 1)])
        elements = page_assembler(self.layer, policy).assemble(page, [], SUBLEVEL).elements
        return [element.text for element in elements if isinstance(element, Paragraph)]

    def test_spans_resuming_beside_their_start_keep_the_abstract_one_paragraph_and_drop_the_sidebar_whole(
            self) -> None:
        self.assertEqual([" ".join(ABSTRACT_LINES)], self.paragraphs())


if __name__ == "__main__":
    unittest.main()
