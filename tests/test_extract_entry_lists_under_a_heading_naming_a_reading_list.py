from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

import vault
from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, PageBlocks
from _extract.layer import TextLayer
from _extract.outline import Heading as OutlineHeading
from _extract.policy import SectionPolicy
from _extract.structure import Paragraph
from _extract_fixtures import page_assembler

FILE_PAGE = 1
FONT_SIZE = 9.0
LINE_PITCH = 11.0
LEFT_MARGIN = 40.0
HANGING_INDENT = 18.0
HEADING_BASELINE = 90.0
FIRST_ENTRY_BASELINE = 112.0
HEADING_BOX = (38.0, 80.0, 140.0, 93.0)
ENTRIES_BOX = (38.0, 100.0, 400.0, 200.0)
READING_LIST_HEADINGS = ("Further Reading", "Suggested Readings", "Recommended Reading")
ENTRIES = [["Brink, K. (2003) On Forgiveness, in A. Denk (ed.), A Guide", "(pp. 243-64). Amherst: Humanity Books."],
           ["Gram, M. (1978) Moral and Literary Ideals in a Critique of the", "Moral World-View, Clio 7.3: 375-402."],
           ["Robin, J. (1997) Duty and Hypocrisy in a Study of Mind. Toronto:", "University of Toronto Press."]]


class ReadingListPdf:
    def __init__(self, path: Path, heading: str) -> None:
        self._path = path
        self._heading = heading

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_text((LEFT_MARGIN, HEADING_BASELINE), self._heading, fontname="hebo", fontsize=FONT_SIZE)
            for row, (left, text) in enumerate(self._hanging_lines()):
                page.insert_text((left, FIRST_ENTRY_BASELINE + row * LINE_PITCH), text, fontname="helv",
                                 fontsize=FONT_SIZE)
            document.save(self._path)
        return self._path

    @staticmethod
    def _hanging_lines() -> list[tuple[float, str]]:
        return [(LEFT_MARGIN if row == 0 else LEFT_MARGIN + HANGING_INDENT, text)
                for entry in ENTRIES for row, text in enumerate(entry)]


class TestEntryListsUnderAHeadingNamingAReadingList(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def paragraphs(self, heading: str) -> list[str]:
        layer = TextLayer(ReadingListPdf(self._directory / "reading.pdf", heading).write())
        self.addCleanup(layer.close)
        blocks = [Block(FILE_PAGE, HEADING_KIND, "", HEADING_BOX, {}, "/page/1/SectionHeader/0"),
                  Block(FILE_PAGE, TEXT_KIND, f"<p>{' '.join(' '.join(entry) for entry in ENTRIES)}</p>",
                        ENTRIES_BOX, {}, "/page/1/Text/1")]
        assembled = page_assembler(layer, SectionPolicy.keeping_everything()).assemble(
            PageBlocks(FILE_PAGE, blocks), [OutlineHeading(1, heading, FILE_PAGE)], None)
        return [element.text for element in assembled.elements if isinstance(element, Paragraph)]

    def test_entries_of_one_block_under_a_further_reading_heading_open_one_paragraph_each(self) -> None:
        self.assertEqual([" ".join(entry) for entry in ENTRIES], self.paragraphs(READING_LIST_HEADINGS[0]))

    def test_a_heading_naming_a_reading_list_is_a_bibliography_heading(self) -> None:
        for heading in READING_LIST_HEADINGS:
            with self.subTest(heading=heading):
                self.assertTrue(vault.is_bibliography_heading(heading))


if __name__ == "__main__":
    unittest.main()
