from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.outline import Heading as OutlineHeading
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs
from _extract.writer import NoteWriter

BODY_FONT = "helv"
LABEL_FONT = "heit"
DISPLAY_SIZE = 14.0
BODY_SIZE = 10.0
LEFT = 40.0
LABEL_INDENT = 14.0
RIGHT = 360.0
LINE_PITCH = 12.0
HALF_LINE = 6.0
SECTION = OutlineHeading(1, "3. Modern physics and its claims", 1)
SECTION_BASELINE = 60.0
OPENING_BASELINE = 100.0
OPENING_LINES = ("The modern theories make claims that differ from the classical ones in",
                 "several ways, which the following lists set out for each theory.")
LETTERED_LABEL = "a) Special Theory of Relativity (SR)"
LOWERCASE_LABEL = "b) theory of the general kind"
LABEL_BASELINE = 150.0
LIST_LINES = ("There is no absolute simultaneity independent of the observer",
              "There is a time dilation of moving clocks")


@dataclass(frozen=True)
class PrintedBlock:
    kind: str
    lines: tuple[str, ...]
    baseline: float
    font: str = BODY_FONT
    size: float = BODY_SIZE
    indent: float = 0.0

    def draw_on(self, page) -> None:
        for row, line in enumerate(self.lines):
            page.insert_text((LEFT + self.indent, self.baseline + row * LINE_PITCH), line, fontsize=self.size,
                             fontname=self.font)

    def engine_block(self) -> Block:
        bottom = self.baseline + (len(self.lines) - 1) * LINE_PITCH + HALF_LINE
        box = (LEFT + self.indent, self.baseline - self.size, RIGHT, bottom)
        tag = "h3" if self.kind == HEADING_KIND else "p"
        html = f"<{tag}>{' '.join(self.lines)}</{tag}>"
        return Block(1, self.kind, html, box, {}, f"/page/1/{self.kind}/{self.baseline}")


def printed_page(label: str) -> list[PrintedBlock]:
    label_block = PrintedBlock(HEADING_KIND, (label,), LABEL_BASELINE, LABEL_FONT, indent=LABEL_INDENT)
    list_block = PrintedBlock(TEXT_KIND, LIST_LINES, LABEL_BASELINE + 2 * LINE_PITCH, indent=2 * LABEL_INDENT)
    return [PrintedBlock(HEADING_KIND, (SECTION.title,), SECTION_BASELINE, size=DISPLAY_SIZE),
            PrintedBlock(TEXT_KIND, OPENING_LINES, OPENING_BASELINE), label_block, list_block]


class LabelledListPdf:
    def __init__(self, path: Path, printed: list[PrintedBlock]) -> None:
        self._path = path
        self._printed = printed

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=400.0, height=600.0)
            for block in self._printed:
                block.draw_on(page)
            document.save(self._path)
        return self._path

    def blocks(self) -> DocumentBlocks:
        return DocumentBlocks([PageBlocks(1, [block.engine_block() for block in self._printed])])


class TestHeadingsWhoseCapitalisedTitleFollowsALetteredLabel(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._directory = Path(directory.name)

    def _written(self, label: str) -> str:
        pdf = LabelledListPdf(self._directory / "labelled.pdf", printed_page(label))
        layer = TextLayer(pdf.write())
        self.addCleanup(layer.close)
        inputs = StructureInputs(pdf.blocks(), [SECTION], WorkerReadings.none(), keep_everything())
        structure = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)
        return NoteWriter().render(structure.elements(), structure.definitions()).text

    def test_a_lettered_label_before_a_capitalised_title_opens_a_heading(self) -> None:
        self.assertIn(f"## {LETTERED_LABEL}", self._written(LETTERED_LABEL))

    def test_the_labelled_heading_stands_above_its_list(self) -> None:
        written = self._written(LETTERED_LABEL)
        self.assertLess(written.index(LETTERED_LABEL), written.index(LIST_LINES[0]))

    def test_a_lettered_label_before_a_lowercase_word_opens_no_heading(self) -> None:
        self.assertNotIn(f"## {LOWERCASE_LABEL}", self._written(LOWERCASE_LABEL))


if __name__ == "__main__":
    unittest.main()
