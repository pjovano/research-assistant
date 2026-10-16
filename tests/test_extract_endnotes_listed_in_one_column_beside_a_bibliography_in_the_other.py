from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import FOOTNOTE_KIND, HEADING_KIND, LIST_GROUP_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs
from _extract.writer import NoteWriter

FILE_PAGE = 1
FONT = "helv"
FONT_SIZE = 9.0
PAGE_WIDTH, PAGE_HEIGHT = 800.0, 600.0
LEFT_COLUMN, RIGHT_COLUMN = 40.0, 440.0
COLUMN_WIDTH = 320.0
FIRST_BASELINE = 80.0
LINE_PITCH = 14.0
LINE_HALF_HEIGHT = 8.0
BODY = "The closing sentence of the body."
NOTES_TITLE = "NOTES"
BIBLIOGRAPHY_TITLE = "BIBLIOGRAPHY"
NOTES = ["* Text of a talk given at a symposium.", "1 This is detailed in a later paper."]
ENTRIES = ["[1] A. Abel: 1967, Foundations of Analysis, New York.", "[2] B. Baker: 1974, Theory of Objects, Paris."]
EXPECTED_OPENING = [BODY, f"# {NOTES_TITLE}", *NOTES, f"# {BIBLIOGRAPHY_TITLE}"]


@dataclass(frozen=True)
class PlacedBlock:
    kind: str
    left: float
    first_row: int
    lines: list[str]

    def block(self) -> Block:
        top = baseline_of(self.first_row) - LINE_HALF_HEIGHT
        bottom = baseline_of(self.first_row + len(self.lines) - 1) + LINE_HALF_HEIGHT / 2
        html = "<ul>" + "".join(f"<li>{line}</li>" for line in self.lines) + "</ul>" \
            if self.kind == LIST_GROUP_KIND else f"<p>{' '.join(self.lines)}</p>"
        return Block(FILE_PAGE, self.kind, html, (self.left, top, self.left + COLUMN_WIDTH, bottom), {},
                     f"/page/{FILE_PAGE}/{self.kind}/{self.left}/{self.first_row}")


ENGINE_ORDER = [PlacedBlock(TEXT_KIND, LEFT_COLUMN, 0, [BODY]),
                PlacedBlock(HEADING_KIND, LEFT_COLUMN, 2, [NOTES_TITLE]),
                PlacedBlock(HEADING_KIND, RIGHT_COLUMN, 0, [BIBLIOGRAPHY_TITLE]),
                PlacedBlock(LIST_GROUP_KIND, RIGHT_COLUMN, 1, ENTRIES),
                *[PlacedBlock(FOOTNOTE_KIND, LEFT_COLUMN, 3 + row, [note]) for row, note in enumerate(NOTES)]]


def baseline_of(row: int) -> float:
    return FIRST_BASELINE + row * LINE_PITCH


class TwoColumnPagePdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            for placed in ENGINE_ORDER:
                for offset, line in enumerate(placed.lines):
                    page.insert_text((placed.left, baseline_of(placed.first_row + offset)), line,
                                     fontsize=FONT_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


class TestEndnotesListedInOneColumnBesideABibliographyInTheOther(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._path = Path(directory.name) / "spread.pdf"

    def paragraphs(self) -> list[str]:
        layer = TextLayer(TwoColumnPagePdf(self._path).write())
        self.addCleanup(layer.close)
        reading = DocumentBlocks([PageBlocks(FILE_PAGE, [placed.block() for placed in ENGINE_ORDER])])
        inputs = StructureInputs(reading, [], WorkerReadings.none(), keep_everything())
        structure = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)
        text = NoteWriter().render(structure.elements(), structure.definitions()).text
        return [paragraph.strip() for paragraph in text.strip().split("\n\n")][1:]

    def test_the_notes_follow_their_heading_before_the_other_columns_bibliography(self) -> None:
        self.assertEqual(EXPECTED_OPENING, self.paragraphs()[:len(EXPECTED_OPENING)])


if __name__ == "__main__":
    unittest.main()
