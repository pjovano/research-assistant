from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.layer import TextLayer

PAGE_COUNT = 3
LABEL_TREE_FROM_SECOND_PAGE = "<</Nums[1 <</S/D/St 19>>]>>"
FIRST_FILE_PAGE = 1
SECOND_FILE_PAGE = 2
THIRD_FILE_PAGE = 3


class PdfLabelledFromTheSecondPage:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            for _ in range(PAGE_COUNT):
                document.new_page()
            document.xref_set_key(document.pdf_catalog(), "PageLabels", LABEL_TREE_FROM_SECOND_PAGE)
            document.save(self._path)
        return self._path


class TestPageLabelsBeginningAfterTheFirstPage(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.layer = TextLayer(PdfLabelledFromTheSecondPage(Path(directory.name) / "labelled.pdf").write())

    def test_a_page_before_the_first_label_range_is_unlabelled(self) -> None:
        self.assertIsNone(self.layer.label(FIRST_FILE_PAGE))

    def test_pages_inside_the_first_label_range_take_its_labels(self) -> None:
        self.assertEqual([self.layer.label(SECOND_FILE_PAGE), self.layer.label(THIRD_FILE_PAGE)], ["19", "20"])


if __name__ == "__main__":
    unittest.main()
