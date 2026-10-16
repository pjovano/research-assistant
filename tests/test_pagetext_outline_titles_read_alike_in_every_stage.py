from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

import pagetext
from _extract.outline import Outline

TAB_SEPARATED = "1.2\tIntroduction"
LINE_BROKEN = "Part One\nThe Concept"
MARKED_UP = "<i>Kant</i> &amp; Hegel"
TRUNCATED_COPY = "Reasons for LoReasons for Logic"
RAW_TITLES = (TAB_SEPARATED, LINE_BROKEN, MARKED_UP, TRUNCATED_COPY)
READ_TITLES = ["1.2 Introduction", "Part One The Concept", "Kant & Hegel", "Reasons for Logic"]


class OutlinedPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            for _title in RAW_TITLES:
                document.new_page()
            document.set_toc([[1, title, page] for page, title in enumerate(RAW_TITLES, start=1)])
            document.save(self._path)
        return self._path


class TestOutlineTitlesReadAlikeInEveryStage(unittest.TestCase):
    def setUp(self) -> None:
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory, True)
        self._pdf = OutlinedPdf(directory / "outlined.pdf").write()

    def test_the_outline_entries_read_each_title_with_its_markup_breaks_and_truncated_copy_resolved(self) -> None:
        self.assertEqual(READ_TITLES, [title for _level, title, _page in pagetext.outline_entries(self._pdf)])

    def test_stage_two_reads_the_same_titles_as_the_outline_entries(self) -> None:
        self.assertEqual(READ_TITLES, [heading.title for heading in Outline(self._pdf).headings()])


if __name__ == "__main__":
    unittest.main()
