from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, PageBlocks
from _extract.box import Box
from _extract.layer import TextLayer
from _extract.lists import HangingIndentList
from _extract.outline import Heading as OutlineHeading
from _extract.structure import Heading, Paragraph
from _extract_fixtures import keep_everything, page_assembler

FONT_SIZE = 9.0
LINE_PITCH = 11.0
LEFT_COLUMN, RIGHT_COLUMN = 40.0, 320.0
HANGING_INDENT = 12.0
COLUMN_TOP_BASELINE = 100.0
HEADING_BASELINE = 160.0
FIRST_ENTRY_BASELINE = 182.0
BODY = ["The closing paragraph of the body runs", "down the left column and ends here", "before the list opens."]
HEADING_TITLE = "References"
LEFT_ENTRIES = [["Adams, A. (2001). A first work on", "the question."], ["Baker, B. (2002). A second work."],
                ["Cole, C. (2003). A third work on", "a further question."]]
RIGHT_ENTRIES = [["Dunn, D. (2004). A fourth work on", "another question."], ["Evans, E. (2005). A fifth work."],
                 ["Fox, F. (2006). A sixth work on", "a last question."]]
ENCLOSING_BOX = (36.0, 88.0, 560.0, 240.0)
HEADING_BOX = (38.0, 150.0, 100.0, 163.0)
LEFT_LIST_BOX, RIGHT_LIST_BOX = (38.0, 172.0, 300.0, 240.0), (318.0, 90.0, 560.0, 160.0)
ENCLOSING_ID = "/page/1/Text/0"
HEADING_ID = "/page/1/SectionHeader/1"


class HeadingInsideATwoColumnBlockPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            self._lines(page, [(LEFT_COLUMN, text) for text in BODY], COLUMN_TOP_BASELINE)
            page.insert_text((LEFT_COLUMN, HEADING_BASELINE), HEADING_TITLE, fontname="hebo", fontsize=FONT_SIZE)
            self._lines(page, self._hanging(LEFT_ENTRIES, LEFT_COLUMN), FIRST_ENTRY_BASELINE)
            self._lines(page, self._hanging(RIGHT_ENTRIES, RIGHT_COLUMN), COLUMN_TOP_BASELINE)
            document.save(self._path)
        return self._path

    @staticmethod
    def _hanging(entries: list[list[str]], left: float) -> list[tuple[float, str]]:
        return [(left if row == 0 else left + HANGING_INDENT, text) for entry in entries
                for row, text in enumerate(entry)]

    @staticmethod
    def _lines(page, lines: list[tuple[float, str]], first_baseline: float) -> None:
        for row, (left, text) in enumerate(lines):
            page.insert_text((left, first_baseline + row * LINE_PITCH), text, fontname="helv", fontsize=FONT_SIZE)


def joined(entry: list[str]) -> str:
    return " ".join(entry)


class TestHeadingEnclosedByATextBlock(unittest.TestCase):
    def setUp(self) -> None:
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory, True)
        self._layer = TextLayer(HeadingInsideATwoColumnBlockPdf(directory / "enclosed.pdf").write())
        self.addCleanup(self._layer.close)

    def _assembled(self) -> list:
        assembler = page_assembler(self._layer, keep_everything())
        blocks = [Block(1, TEXT_KIND, "<p>engine text</p>", ENCLOSING_BOX, {}, ENCLOSING_ID),
                  Block(1, HEADING_KIND, "", HEADING_BOX, {}, HEADING_ID)]
        due = [OutlineHeading(1, HEADING_TITLE, 1)]
        return assembler.assemble(PageBlocks(1, blocks), due, None).elements[1:]

    def test_a_text_block_enclosing_a_heading_is_split_at_the_heading_and_its_list_read_below_it(self) -> None:
        expected = [Paragraph(" ".join(BODY), False, 1), Heading(1, HEADING_TITLE, 1)]
        expected += [Paragraph(joined(entry), False, 1) for entry in LEFT_ENTRIES + RIGHT_ENTRIES]
        self.assertEqual(expected, [self._comparable(element) for element in self._assembled()])

    def test_an_entry_list_reads_only_the_lines_its_blocks_hold_not_every_line_their_boxes_span(self) -> None:
        boxes = [Box.of(LEFT_LIST_BOX), Box.of(RIGHT_LIST_BOX)]
        entries = [entry.text for entry in HangingIndentList(self._layer).boxed_entries(1, boxes)]
        self.assertEqual([joined(entry) for entry in LEFT_ENTRIES + RIGHT_ENTRIES], entries)

    @staticmethod
    def _comparable(element):
        if isinstance(element, Paragraph):
            return Paragraph(element.text, False, element.file_page)
        return element


if __name__ == "__main__":
    unittest.main()
