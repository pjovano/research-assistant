from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.furniture import WorkFurniture
from _extract.layer import TextLayer

LEFT = 72.0
RUNNING_HEAD_SIZE = 8.0
HEADING_SIZE = 12.0
BODY_SIZE = 10.0
RUNNING_HEAD_BASELINE = 42.0
HEADING_BASELINES = (70.0, 84.0)
BODY_BASELINE = 110.0
HEADER_KIND = "PageHeader"
RUNNING_HEAD = "SKEPTICISM ABOUT TESTED KNOWLEDGE"
HEADING_LINES = ("5 SKEPTICISM ABOUT TESTED KNOWLEDGE:", "SOME DIFFICULTIES")
BODY_LINE = "The main problem with this account is that it cannot tell the two apart."
HEADER_BOX = (70.0, 32.0, 400.0, 45.0)
HEADING_BOX = (70.0, 58.0, 400.0, 88.0)
BODY_BOX = (70.0, 100.0, 450.0, 114.0)
FOLIOS = (690, 691)


class RunningHeadedPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self, heading_size: float) -> Path:
        with pymupdf.open() as document:
            for folio in FOLIOS:
                page = document.new_page()
                page.insert_text((LEFT, RUNNING_HEAD_BASELINE), f"{folio} {RUNNING_HEAD}", fontsize=RUNNING_HEAD_SIZE)
                page.insert_text((LEFT, BODY_BASELINE), BODY_LINE, fontsize=BODY_SIZE)
            page = document.new_page()
            for baseline, line in zip(HEADING_BASELINES, HEADING_LINES):
                page.insert_text((LEFT, baseline), line, fontsize=heading_size)
            page.insert_text((LEFT, BODY_BASELINE), BODY_LINE, fontsize=BODY_SIZE)
            document.save(self._path)
        return self._path


def page_blocks(file_page: int, printed: list[tuple[str, str, tuple]]) -> PageBlocks:
    return PageBlocks(file_page, [Block(file_page, kind, f"<p>{text}</p>", box, {}, f"/page/{file_page}/{kind}/{index}")
                                  for index, (kind, text, box) in enumerate(printed)])


def document_blocks() -> DocumentBlocks:
    body = (TEXT_KIND, BODY_LINE, BODY_BOX)
    headed = [page_blocks(page, [(HEADER_KIND, f"{folio} {RUNNING_HEAD}", HEADER_BOX), body])
              for page, folio in enumerate(FOLIOS, start=1)]
    opening = page_blocks(len(FOLIOS) + 1, [(HEADING_KIND, " ".join(HEADING_LINES), HEADING_BOX), body])
    return DocumentBlocks(headed + [opening])


class TestAHeadingLineReadingAsTheRunningHead(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def _opening_page(self, heading_size: float) -> PageBlocks:
        layer = TextLayer(RunningHeadedPdf(self._directory / "headed.pdf").write(heading_size))
        self.addCleanup(layer.close)
        return WorkFurniture(layer).refiled(document_blocks()).pages[-1]

    def test_a_heading_line_set_larger_than_the_running_head_it_reads_like_stays_in_the_heading(self) -> None:
        page = self._opening_page(HEADING_SIZE)
        self.assertEqual([], page.furniture_texts)

    def test_the_heading_keeps_its_first_line_when_set_larger_than_the_running_head(self) -> None:
        heading = self._opening_page(HEADING_SIZE).content[0]
        self.assertEqual(HEADING_BOX[1], heading.bbox.top)

    def test_a_top_line_set_in_the_running_heads_type_is_still_split_off_as_one(self) -> None:
        page = self._opening_page(RUNNING_HEAD_SIZE)
        self.assertEqual([HEADING_LINES[0]], page.furniture_texts)


if __name__ == "__main__":
    unittest.main()
