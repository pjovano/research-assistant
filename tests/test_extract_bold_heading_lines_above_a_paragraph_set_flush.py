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

FONT = "helv"
DISPLAY_SIZE = 18.0
BODY_SIZE = 10.0
LEFT = 40.0
RIGHT = 360.0
PARAGRAPH_INDENT = 12.0
LINE_PITCH = 12.0
HALF_LINE = 6.0
TITLE_BASELINE = 60.0
FLUSH_BASELINE = 120.0
INDENTED_BASELINE = 160.0
CHAPTER_TITLE = "18 A Chapter on Pleasure"
FLUSH_LINES = ("In 1931 the author published his first book, a study of the", "dialogue and its ethics.")
INDENTED_LINES = ("The book is really two extended essays, the first on the", "dialogue and the second on its method.")
LATER_SECTION = OutlineHeading(1, "References", 2)


@dataclass(frozen=True)
class PrintedParagraph:
    baseline: float
    lines: tuple[str, ...]
    opening_indent: float = 0.0

    def draw_on(self, page) -> None:
        for row, line in enumerate(self.lines):
            indent = self.opening_indent if row == 0 else 0.0
            page.insert_text((LEFT + indent, self.baseline + row * LINE_PITCH), line, fontsize=BODY_SIZE,
                             fontname=FONT)

    def engine_block(self, file_page: int) -> Block:
        return PrintedBlock(TEXT_KIND, " ".join(self.lines), self.baseline, len(self.lines)).on(file_page)


@dataclass(frozen=True)
class PrintedBlock:
    kind: str
    text: str
    baseline: float
    rows: int = 1

    def on(self, file_page: int) -> Block:
        box = (LEFT, self.baseline - DISPLAY_SIZE, RIGHT, self.baseline + (self.rows - 1) * LINE_PITCH + HALF_LINE)
        identifier = f"/page/{file_page}/{self.kind}/{self.baseline}"
        return Block(file_page, self.kind, f"<p>{self.text}</p>", box, {}, identifier)


FLUSH = PrintedParagraph(FLUSH_BASELINE, FLUSH_LINES)
INDENTED = PrintedParagraph(INDENTED_BASELINE, INDENTED_LINES, PARAGRAPH_INDENT)


class ChapterOpeningPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=400.0, height=600.0)
            page.insert_text((LEFT, TITLE_BASELINE), CHAPTER_TITLE, fontsize=DISPLAY_SIZE, fontname=FONT)
            FLUSH.draw_on(page)
            INDENTED.draw_on(page)
            document.new_page(width=400.0, height=600.0).insert_text((LEFT, TITLE_BASELINE), LATER_SECTION.title,
                                                                    fontsize=DISPLAY_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


def engine_reading() -> DocumentBlocks:
    opening = PageBlocks(1, [PrintedBlock(HEADING_KIND, CHAPTER_TITLE, TITLE_BASELINE).on(1),
                             FLUSH.engine_block(1), INDENTED.engine_block(1)])
    later = PageBlocks(2, [PrintedBlock(HEADING_KIND, LATER_SECTION.title, TITLE_BASELINE).on(2)])
    return DocumentBlocks([opening, later])


class TestBoldHeadingLinesAboveAParagraphSetFlush(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(ChapterOpeningPdf(Path(directory.name) / "chapter.pdf").write())
        self.addCleanup(layer.close)
        inputs = StructureInputs(engine_reading(), [LATER_SECTION], WorkerReadings.none(), keep_everything())
        structure = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)
        self.blocks = NoteWriter().render(structure.elements(), structure.definitions()).text.split("\n\n")

    def test_the_heading_line_stands_as_a_bold_block_of_its_own(self) -> None:
        self.assertIn(f"**{CHAPTER_TITLE}**", self.blocks)

    def test_the_flush_paragraph_below_opens_a_block_of_its_own(self) -> None:
        self.assertIn(" ".join(FLUSH_LINES), self.blocks)


if __name__ == "__main__":
    unittest.main()
