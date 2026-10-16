from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs
from _extract.writer import NoteWriter

DIAGRAM_KIND = "Diagram"
FONT = "helv"
BODY_SIZE = 10.0
NOTE_SIZE = 7.0
DISPLAY_SIZE = 20.0
LEFT = 40.0
RIGHT = 360.0
LINE_PITCH = 12.0
LABEL_PITCH = 30.0
HALF_LINE = 6.0
BOX_MARGIN = 10.0
PAGE_WIDTH = 400.0
PAGE_HEIGHT = 600.0
ABOVE_BASELINE = 80.0
DIAGRAM_BASELINE = 140.0
BELOW_BASELINE = 320.0
ABOVE = ("The structure of the subject took the form of a",
         "bifurcating scheme of oppositions, set out below:")
BELOW = ("This last scheme served as the basis of teaching",
         "for many centuries after it was first proposed.")
WORDED_LABELS = ("Knowledge", "divided into", "The finite The infinite")
LETTERED_LABELS = ("A f B", "g h", "C k D")
MOSTLY_LETTERED_LABELS = ("A f B", "maps", "C k D")
MOSTLY_WORDED_LABELS = ("Source arrow Target", "g", "Image under map")


@dataclass(frozen=True)
class PrintedLines:
    kind: str
    baseline: float
    lines: tuple[str, ...]
    size: float = BODY_SIZE
    pitch: float = LINE_PITCH

    def draw_on(self, page) -> None:
        for row, line in enumerate(self.lines):
            page.insert_text((LEFT + BOX_MARGIN, self.baseline + row * self.pitch), line, fontsize=self.size,
                             fontname=FONT)

    def engine_block(self, file_page: int) -> Block:
        identifier = f"/page/{file_page}/{self.kind}/{self.baseline}"
        html = "" if self.kind == DIAGRAM_KIND else f"<p>{' '.join(self.lines)}</p>"
        return Block(file_page, self.kind, html, self.box(), {}, identifier)

    def box(self) -> tuple[float, float, float, float]:
        return (LEFT, self.baseline - self.size - HALF_LINE, RIGHT,
                self.baseline + (len(self.lines) - 1) * self.pitch + HALF_LINE)


class RuledDiagramPdf:
    def __init__(self, path: Path, diagram: PrintedLines) -> None:
        self._path = path
        self._diagram = diagram
        self._printed = [PrintedLines(TEXT_KIND, ABOVE_BASELINE, ABOVE), diagram,
                         PrintedLines(TEXT_KIND, BELOW_BASELINE, BELOW)]

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            for lines in self._printed:
                lines.draw_on(page)
            page.draw_rect(pymupdf.Rect(*self._diagram.box()), color=(0, 0, 0))
            document.save(self._path)
        return self._path

    def blocks(self) -> DocumentBlocks:
        return DocumentBlocks([PageBlocks(1, [lines.engine_block(1) for lines in self._printed])])


class TestDiagramsLabelledInWordsAtTheBodyTypeSize(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._directory = Path(directory.name)

    def _written(self, labels: tuple[str, ...], size: float = BODY_SIZE) -> str:
        diagram = PrintedLines(DIAGRAM_KIND, DIAGRAM_BASELINE, labels, size, LABEL_PITCH)
        pdf = RuledDiagramPdf(self._directory / "diagram.pdf", diagram)
        layer = TextLayer(pdf.write())
        self.addCleanup(layer.close)
        inputs = StructureInputs(pdf.blocks(), [], WorkerReadings.none(), keep_everything())
        structure = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)
        return NoteWriter().render(structure.elements(), structure.definitions()).text

    def test_labels_in_words_at_the_body_size_are_written_one_line_each(self) -> None:
        self.assertIn("\n".join(WORDED_LABELS), self._written(WORDED_LABELS))

    def test_labels_in_words_stand_between_the_paragraphs_around_the_diagram(self) -> None:
        written = self._written(WORDED_LABELS)
        self.assertLess(written.index(ABOVE[-1]), written.index(WORDED_LABELS[0]))
        self.assertLess(written.index(WORDED_LABELS[-1]), written.index(BELOW[0]))

    def test_labels_mostly_in_words_are_written(self) -> None:
        self.assertIn("\n".join(MOSTLY_WORDED_LABELS), self._written(MOSTLY_WORDED_LABELS))

    def test_labels_in_single_letters_are_left_out(self) -> None:
        self.assertNotIn(LETTERED_LABELS[0], self._written(LETTERED_LABELS))

    def test_labels_mostly_in_single_letters_are_left_out(self) -> None:
        self.assertNotIn(MOSTLY_LETTERED_LABELS[1], self._written(MOSTLY_LETTERED_LABELS))

    def test_labels_in_words_set_below_the_body_size_are_left_out(self) -> None:
        self.assertNotIn(WORDED_LABELS[0], self._written(WORDED_LABELS, NOTE_SIZE))

    def test_labels_in_words_set_above_the_body_size_are_left_out(self) -> None:
        self.assertNotIn(WORDED_LABELS[0], self._written(WORDED_LABELS, DISPLAY_SIZE))


if __name__ == "__main__":
    unittest.main()
