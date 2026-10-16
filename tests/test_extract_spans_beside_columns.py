from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import pymupdf

from _extract.blocks import TEXT_KIND, Block
from _extract.layer import TextLayer
from _extract.policy import SectionPolicy
from _extract.spans import ScopePoints

LEFT_COLUMN_X, RIGHT_COLUMN_X = 40.0, 300.0
FIRST_BASELINE, LINE_PITCH = 100.0, 10.0
RIGHT_COLUMN_OFFSET = 1.0
LEFT_LINES = ("Received 1 May 2020", "Available online 9 June 2020", "Keywords:")
RIGHT_LINES = ("An abstract opens beside the article history,", "runs on beside the online date,",
               "and closes beside the keywords.")
BLOCK_PADDING = 3.0
LEFT_BLOCK_RIGHT, RIGHT_BLOCK_RIGHT = 200.0, 560.0


class TwoColumnFrontMatterPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as doc:
            page = doc.new_page()
            for row, (left, right) in enumerate(zip(LEFT_LINES, RIGHT_LINES)):
                baseline = FIRST_BASELINE + row * LINE_PITCH
                page.insert_text((LEFT_COLUMN_X, baseline), left)
                page.insert_text((RIGHT_COLUMN_X, baseline + RIGHT_COLUMN_OFFSET), right)
            doc.save(self._path)
        return self._path


class TestSpanStartingBesideItsResumeLine(unittest.TestCase):
    def setUp(self) -> None:
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory)
        self.layer = TextLayer(TwoColumnFrontMatterPdf(directory / "front.pdf").write())
        self.policy = SectionPolicy(ScopePoints(self.layer).spans([(f"1: {LEFT_LINES[1]}", f"1: {RIGHT_LINES[1]}")]))

    def _block_around(self, text: str, right: float) -> Block:
        line = next(line for line in self.layer.lines(1) if line.text.strip() == text)
        box = line.box
        padded = (box.left - BLOCK_PADDING, box.top - BLOCK_PADDING, right, box.bottom + BLOCK_PADDING)
        return Block(1, TEXT_KIND, "", padded, {}, f"/page/0/Text/{text}")

    def test_a_span_resuming_at_the_line_beside_its_start_line_drops_the_block_of_its_start_line(self) -> None:
        self.assertFalse(self.policy.keeps_block(self._block_around(LEFT_LINES[1], LEFT_BLOCK_RIGHT)))

    def test_a_span_resuming_at_the_line_beside_its_start_line_keeps_the_block_beside_it(self) -> None:
        self.assertTrue(self.policy.keeps_block(self._block_around(RIGHT_LINES[1], RIGHT_BLOCK_RIGHT)))

    def test_a_span_resuming_at_the_line_beside_its_start_line_keeps_the_line_below_its_start_line(self) -> None:
        self.assertTrue(self.policy.keeps_block(self._block_around(LEFT_LINES[2], LEFT_BLOCK_RIGHT)))


if __name__ == "__main__":
    unittest.main()
