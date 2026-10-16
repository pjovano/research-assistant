from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.elements import Heading, Paragraph
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

FONT = "tiro"
BOLD_FONT = "tibo"
BODY_SIZE = 10.0
LEFT = 40.0
RIGHT = 500.0
FIRST_BASELINE = 80.0
LINE_PITCH = 40.0
LINE_HALF_HEIGHT = 6.0
LEAD_IN = "As a first instance of the schema, let us take a judgement of reflection proposed in the Logic:"
EXAMPLE = "(1) Man is mortal"
FOLLOWING = "(see WL: 643). When we assert (1), we do not ascribe a property to a concept."
BOLD_NUMBERED_HEADING = "(i) Nonlinear Justification"


class ExamplePagePdf:
    def __init__(self, path: Path, lines: list[tuple[str, str, str]]) -> None:
        self._path = path
        self._lines = lines

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=RIGHT + LEFT)
            for row, (_kind, text, font) in enumerate(self._lines):
                page.insert_text((LEFT, _baseline(row)), text, fontsize=BODY_SIZE, fontname=font)
            document.save(self._path)
        return self._path

    def blocks(self) -> DocumentBlocks:
        return DocumentBlocks([PageBlocks(1, [_engine_block(row, line) for row, line in enumerate(self._lines)])])


def _baseline(row: int) -> float:
    return FIRST_BASELINE + row * LINE_PITCH


def _engine_block(row: int, line: tuple[str, str, str]) -> Block:
    kind, text, _font = line
    baseline = _baseline(row)
    box = (LEFT, baseline - BODY_SIZE - LINE_HALF_HEIGHT, RIGHT, baseline + LINE_HALF_HEIGHT)
    tag = "h2" if kind == HEADING_KIND else "p"
    return Block(1, kind, f"<{tag}>{text}</{tag}>", box, {}, f"/page/1/{kind}/{row}")


class TestNumberedDisplayLinesSetInTheBodyType(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._directory = Path(directory.name)

    def _written(self, line_between: tuple[str, str, str]) -> list[tuple[str, str]]:
        lines = [(TEXT_KIND, LEAD_IN, FONT), line_between, (TEXT_KIND, FOLLOWING, FONT)]
        pdf = ExamplePagePdf(self._directory / "example.pdf", lines)
        layer = TextLayer(pdf.write())
        self.addCleanup(layer.close)
        inputs = StructureInputs(pdf.blocks(), [], WorkerReadings.none(), keep_everything())
        elements = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs).elements()
        return [(type(element).__name__, element.title if isinstance(element, Heading) else element.text)
                for element in elements if isinstance(element, (Heading, Paragraph))]

    def test_a_numbered_example_in_the_body_type_the_engine_reads_as_a_heading_is_written_as_a_line(self) -> None:
        self.assertIn((Paragraph.__name__, EXAMPLE), self._written((HEADING_KIND, EXAMPLE, FONT)))

    def test_a_numbered_heading_in_a_type_apart_from_the_body_stays_a_heading(self) -> None:
        written = self._written((HEADING_KIND, BOLD_NUMBERED_HEADING, BOLD_FONT))
        self.assertIn((Heading.__name__, BOLD_NUMBERED_HEADING), written)


if __name__ == "__main__":
    unittest.main()
