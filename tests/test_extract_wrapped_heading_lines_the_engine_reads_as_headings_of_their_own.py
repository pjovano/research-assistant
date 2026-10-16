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
from _extract.elements import Heading, Paragraph
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.outline import Outline
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

FONT = "helv"
DISPLAY_SIZE = 12.0
BODY_SIZE = 10.0
PAGE_WIDTH = 612.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 572.0
FIRST_BASELINE = 80.0
LINE_PITCH = 40.0
LINE_HALF_HEIGHT = 12.0
SENTENCE = "The section opens with a sentence of its own."
NUMBERED_FIRST_LINE = "0.3 Intrinsic Metavocabularies for Reason Relations and Conceptual"
NUMBERED_SECOND_LINE = "Contents: Logic"
NUMBERED_TITLE = f"{NUMBERED_FIRST_LINE} {NUMBERED_SECOND_LINE}"
PART_LABEL = "Part III"
PART_FIRST_LINE = "Subjective Intuitions and"
PART_SECOND_LINE = "Objective Structures"
PART_TITLE = f"III {PART_FIRST_LINE} {PART_SECOND_LINE}"
TITLE = "Intuitive and Discursive Understanding"
SUBHEADING = "Understanding and Its Objects"


@dataclass(frozen=True)
class PrintedLine:
    text: str
    kind: str = HEADING_KIND
    size: float = DISPLAY_SIZE

    @property
    def html(self) -> str:
        tag = "h2" if self.kind == HEADING_KIND else "p"
        return f"<{tag}>{self.text}</{tag}>"


class WrappedHeadingPdf:
    def __init__(self, path: Path, lines: list[PrintedLine], outline_title: str) -> None:
        self._path = path
        self._lines = lines + [PrintedLine(SENTENCE, TEXT_KIND, BODY_SIZE)]
        self._outline_title = outline_title

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            for row, line in enumerate(self._lines):
                page.insert_text((LEFT, _baseline(row)), line.text, fontsize=line.size, fontname=FONT)
            document.set_toc([[1, self._outline_title, 1]])
            document.save(self._path)
        return self._path

    @property
    def blocks(self) -> DocumentBlocks:
        return DocumentBlocks([PageBlocks(1, [_engine_block(row, line) for row, line in enumerate(self._lines)])])


def _baseline(row: int) -> float:
    return FIRST_BASELINE + row * LINE_PITCH


def _engine_block(row: int, line: PrintedLine) -> Block:
    baseline = _baseline(row)
    box = (LEFT, baseline - line.size - LINE_HALF_HEIGHT / 2, RIGHT, baseline + LINE_HALF_HEIGHT / 2)
    return Block(1, line.kind, line.html, box, {}, f"/page/1/{line.kind}/{row}")


class TestWrappedHeadingLinesTheEngineReadsAsHeadingsOfTheirOwn(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._directory = Path(directory.name)

    def _written(self, lines: list[PrintedLine], outline_title: str) -> list[str]:
        pdf = WrappedHeadingPdf(self._directory / "wrapped.pdf", lines, outline_title)
        pdf_path = pdf.write()
        layer = TextLayer(pdf_path)
        self.addCleanup(layer.close)
        inputs = StructureInputs(pdf.blocks, Outline(pdf_path).headings(), WorkerReadings.none(), keep_everything())
        elements = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs).elements()
        return [element.title if isinstance(element, Heading) else element.text for element in elements
                if isinstance(element, (Heading, Paragraph))]

    def test_the_wrapped_line_of_a_numbered_title_is_written_once_within_the_outline_title(self) -> None:
        lines = [PrintedLine(NUMBERED_FIRST_LINE), PrintedLine(NUMBERED_SECOND_LINE)]
        self.assertEqual([NUMBERED_TITLE, SENTENCE], self._written(lines, NUMBERED_TITLE))

    def test_the_wrapped_line_of_a_title_under_a_part_label_is_written_once_within_the_outline_title(self) -> None:
        lines = [PrintedLine(PART_LABEL), PrintedLine(PART_FIRST_LINE), PrintedLine(PART_SECOND_LINE)]
        self.assertEqual([PART_TITLE, SENTENCE], self._written(lines, PART_TITLE))

    def test_a_heading_below_the_title_that_continues_none_of_its_words_stays_a_heading(self) -> None:
        lines = [PrintedLine(TITLE), PrintedLine(SUBHEADING)]
        self.assertEqual([TITLE, SUBHEADING, SENTENCE], self._written(lines, TITLE))


if __name__ == "__main__":
    unittest.main()
