from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import PrintedWork, keep_everything, page_assembler
from test_extract_entry_lists_the_engine_reads_from_pixels_joining_two_entries_in_one_paragraph import (
    AUTHOR_LED, ENDS_SHORT, FILE_PAGE, FILLS, REPEATED_AUTHOR, RUN_ON, RecognizedBibliographyScanPdf, engine_reading,
    entry_texts, printed_lines,
)
from _extract.blocks import PageBlocks
from _extract.layer import TextLayer
from _extract.structure import Paragraph

DASH_RUN_ENTRIES = [
    [(AUTHOR_LED, "Adams, Anna (1969). Zum Wahrheitsproblem. Kant-Studien 60.", FILLS)],
    [(REPEATED_AUTHOR, "— (1971). Erscheinung bei Kant. Berlin: Gruyter.", ENDS_SHORT)],
    [(AUTHOR_LED, "Baker, Bernd (2014). Kant on the Cosmological Argument.", FILLS),
     (RUN_ON, "Imprint 14.12: 1-21.", ENDS_SHORT)],
    [(REPEATED_AUTHOR, "— (2016). Kant on Existence. Oxford: Clarendon.", ENDS_SHORT)]]


class TestEntryListsReadFromPixelsWhoseEntriesShareOneEngineBlock(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._pdf = RecognizedBibliographyScanPdf(Path(directory.name) / "scan.pdf")

    def _written_paragraphs(self) -> list[str]:
        layer = TextLayer(self._pdf.write(DASH_RUN_ENTRIES))
        self.addCleanup(layer.close)
        assembler = page_assembler(layer, keep_everything(), PrintedWork(pixel_pages=frozenset({FILE_PAGE})))
        blocks = engine_reading(entry_texts(DASH_RUN_ENTRIES), len(printed_lines(DASH_RUN_ENTRIES)))
        result = assembler.assemble(PageBlocks(FILE_PAGE, blocks), [], 1)
        return [element.text for element in result.elements if isinstance(element, Paragraph)]

    def test_each_entry_the_engine_sets_as_a_paragraph_of_the_block_is_a_paragraph_of_its_own(self) -> None:
        self.assertEqual(entry_texts(DASH_RUN_ENTRIES), self._written_paragraphs())


if __name__ == "__main__":
    unittest.main()
