from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import keep_everything, page_assembler
from _extract.blocks import PageBlocks
from _extract.layer import TextLayer
from _extract.structure import Paragraph

FILE_PAGE = 1
SCAN_GREY = 230
SCAN_PIXELS = pymupdf.IRect(0, 0, 60, 80)
PAGE_WIDTH, PAGE_HEIGHT = 396.0, 656.0
ENTRIES = ["Abel, A. (1970). A semantic analysis of conditionals, Theoria 36: 23-42.",
           "Baker, B. (1977). Toward a theory of representation, in C. Carr (ed.), Studies 2, 42-6.",
           "Dunn, D. (1983). From Psychology to Science, Bradford Books, Cambridge, Mass."]


class ScannedPagePdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            scan = pymupdf.Pixmap(pymupdf.csGRAY, SCAN_PIXELS, False)
            scan.set_rect(scan.irect, (SCAN_GREY,))
            page.insert_image(page.rect, pixmap=scan, keep_proportion=False)
            document.save(self._path)
        return self._path


class TestEntryListsOnAPageAWorkerTranscribesOneEntryToALine(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._path = Path(directory.name) / "scan.pdf"

    def paragraphs(self, transcription: str) -> list[str]:
        layer = TextLayer(ScannedPagePdf(self._path).write())
        self.addCleanup(layer.close)
        result = page_assembler(layer, keep_everything()).transcribed(PageBlocks(FILE_PAGE, []), transcription, [])
        return [element.text for element in result.elements if isinstance(element, Paragraph)]

    def test_each_line_of_the_transcription_is_a_paragraph_of_its_own(self) -> None:
        self.assertEqual(ENTRIES, self.paragraphs("\n".join(ENTRIES)))

    def test_a_blank_line_between_entries_opens_no_empty_paragraph(self) -> None:
        self.assertEqual(ENTRIES, self.paragraphs("\n\n".join(ENTRIES)))


if __name__ == "__main__":
    unittest.main()
