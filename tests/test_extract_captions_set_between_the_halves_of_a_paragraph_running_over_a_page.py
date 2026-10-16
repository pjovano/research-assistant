from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import CAPTION_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs
from _extract.writer import NoteWriter

FONT = "helv"
BODY_SIZE = 10.0
CAPTION_SIZE = 9.0
LEFT = 40.0
RIGHT = 360.0
LINE_PITCH = 12.0
OPENING_INDENT = 12.0
HALF_LINE = 6.0
PAGE_WIDTH = 400.0
PAGE_HEIGHT = 600.0
TOP_BASELINE = 80.0
CAPTION_BASELINE = 200.0
BELOW_CAPTION_BASELINE = 240.0
CAPTION = "Figure 3.1 A bundle over the base space"
BROKEN_OFF = ("Above each vertex is a fibre of the values that",
              "the variable takes, and an edge joins two values",
              "in adjacent fibres precisely when the")
RUNNING_ON = ("corresponding joint outcome is possible.",)
ENDING_A_SENTENCE = ("Above each vertex is a fibre of the values that",
                     "the variable takes, and an edge joins two values",
                     "in adjacent fibres when their outcome is possible.")
OPENING_ANEW = ("Next we consider the second model displayed",
                "as a bundle on the right of the figure.")


@dataclass(frozen=True)
class PrintedLines:
    kind: str
    baseline: float
    lines: tuple[str, ...]
    size: float = BODY_SIZE
    opening_indent: float = 0.0

    def draw_on(self, page) -> None:
        for row, line in enumerate(self.lines):
            indent = self.opening_indent if row == 0 else 0.0
            page.insert_text((LEFT + indent, self.baseline + row * LINE_PITCH), line, fontsize=self.size,
                             fontname=FONT)

    def engine_block(self, file_page: int) -> Block:
        box = (LEFT, self.baseline - self.size - HALF_LINE, RIGHT,
               self.baseline + (len(self.lines) - 1) * LINE_PITCH + HALF_LINE)
        identifier = f"/page/{file_page}/{self.kind}/{self.baseline}"
        return Block(file_page, self.kind, f"<p>{' '.join(self.lines)}</p>", box, {}, identifier)


class FigureAtThePageTopPdf:
    def __init__(self, path: Path, first_page: PrintedLines, below_the_caption: PrintedLines) -> None:
        self._path = path
        self._pages = ([first_page], [PrintedLines(CAPTION_KIND, CAPTION_BASELINE, (CAPTION,), CAPTION_SIZE),
                                      below_the_caption])

    def write(self) -> Path:
        with pymupdf.open() as document:
            for printed in self._pages:
                page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
                for lines in printed:
                    lines.draw_on(page)
            document.save(self._path)
        return self._path

    def blocks(self) -> DocumentBlocks:
        return DocumentBlocks([PageBlocks(number, [lines.engine_block(number) for lines in printed])
                               for number, printed in enumerate(self._pages, start=1)])


class TestCaptionsSetBetweenTheHalvesOfAParagraphRunningOverAPage(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._directory = Path(directory.name)

    def _written_blocks(self, first_page: tuple[str, ...], below_the_caption: tuple[str, ...],
                        below_indent: float = 0.0) -> list[str]:
        opening = PrintedLines(TEXT_KIND, TOP_BASELINE, first_page, opening_indent=OPENING_INDENT)
        below = PrintedLines(TEXT_KIND, BELOW_CAPTION_BASELINE, below_the_caption, opening_indent=below_indent)
        pdf = FigureAtThePageTopPdf(self._directory / "figure.pdf", opening, below)
        layer = TextLayer(pdf.write())
        self.addCleanup(layer.close)
        inputs = StructureInputs(pdf.blocks(), [], WorkerReadings.none(), keep_everything())
        structure = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)
        return NoteWriter().render(structure.elements(), structure.definitions()).text.strip().split("\n\n")

    def _block_holding(self, words: str, blocks: list[str]) -> int:
        return next(index for index, block in enumerate(blocks) if words in block)

    def test_the_paragraph_runs_on_past_the_caption(self) -> None:
        blocks = self._written_blocks(BROKEN_OFF, RUNNING_ON)
        self.assertEqual(self._block_holding(BROKEN_OFF[-1], blocks), self._block_holding(RUNNING_ON[0], blocks))

    def test_the_caption_stands_as_a_block_of_its_own(self) -> None:
        self.assertIn(CAPTION, self._written_blocks(BROKEN_OFF, RUNNING_ON))

    def test_the_caption_follows_the_paragraph_it_interrupted(self) -> None:
        blocks = self._written_blocks(BROKEN_OFF, RUNNING_ON)
        self.assertLess(self._block_holding(RUNNING_ON[0], blocks), blocks.index(CAPTION))

    def test_a_caption_above_a_paragraph_opening_anew_stays_above_it(self) -> None:
        blocks = self._written_blocks(ENDING_A_SENTENCE, OPENING_ANEW, OPENING_INDENT)
        self.assertLess(blocks.index(CAPTION), self._block_holding(OPENING_ANEW[0], blocks))

    def test_a_capitalised_paragraph_set_flush_below_the_caption_stays_below_it(self) -> None:
        blocks = self._written_blocks(BROKEN_OFF, OPENING_ANEW)
        self.assertLess(blocks.index(CAPTION), self._block_holding(OPENING_ANEW[0], blocks))

    def test_a_paragraph_never_runs_on_into_a_caption(self) -> None:
        blocks = self._written_blocks(ENDING_A_SENTENCE, RUNNING_ON)
        self.assertIn(CAPTION, blocks)


if __name__ == "__main__":
    unittest.main()
