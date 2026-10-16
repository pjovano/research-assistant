from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.outline import Outline
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs
from _extract.writer import NoteWriter

FONT = "cour"
FONT_SIZE = 9.0
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
FIRST_BASELINE = 100.0
LINE_PITCH = 20.0
LINE_HALF_HEIGHT = 8.0
SECTION_LEVEL = 1
REFERENCES_TITLE = "References"
PROOFS_TITLE = "Supplementary proofs"
ENTRIES = ["[1] Brandom, R.: Making it explicit (1994)", "[2] MacLane, S.: Categories (1971)"]
LAST_ENTRY_AUTHOR = "MacLane"
PROOF = "Let f be a monotone map."
LINES = [REFERENCES_TITLE, *ENTRIES, PROOF]
PROOF_ROW = len(LINES) - 1
REFERENCES_DESTINATION_DEPTH = 80.0
PROOFS_DESTINATION_DEPTH = FIRST_BASELINE + PROOF_ROW * LINE_PITCH - LINE_PITCH / 2


def baseline_of(row: int) -> float:
    return FIRST_BASELINE + row * LINE_PITCH


class ReferencesThenProofsPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            for row, line in enumerate(LINES):
                page.insert_text((LEFT, baseline_of(row)), line, fontsize=FONT_SIZE, fontname=FONT)
            document.set_toc([
                [SECTION_LEVEL, REFERENCES_TITLE, 1, {"kind": 1, "to": pymupdf.Point(0, REFERENCES_DESTINATION_DEPTH)}],
                [SECTION_LEVEL, PROOFS_TITLE, 1, {"kind": 1, "to": pymupdf.Point(0, PROOFS_DESTINATION_DEPTH)}]])
            document.save(self._path)
        return self._path


def engine_reading() -> list[PageBlocks]:
    blocks = [Block(1, HEADING_KIND if line == REFERENCES_TITLE else TEXT_KIND, f"<p>{line}</p>",
                    (LEFT, baseline_of(row) - LINE_HALF_HEIGHT, RIGHT, baseline_of(row) + LINE_HALF_HEIGHT / 2), {},
                    f"/page/1/{row}")
              for row, line in enumerate(LINES)]
    return [PageBlocks(1, blocks)]


def written_paragraphs() -> list[str]:
    with tempfile.TemporaryDirectory() as directory:
        pdf_path = ReferencesThenProofsPdf(Path(directory) / "references.pdf").write()
        layer = TextLayer(pdf_path)
        try:
            work = WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts())
            inputs = StructureInputs(DocumentBlocks(engine_reading()), Outline(pdf_path).headings(),
                                     WorkerReadings.none(), keep_everything())
            structure = NoteStructure(work, inputs)
            text = NoteWriter().render(structure.elements(), structure.definitions()).text
        finally:
            layer.close()
    return text.strip().split("\n\n")


def position_of(paragraphs: list[str], words: str) -> int:
    return next(index for index, paragraph in enumerate(paragraphs) if words in paragraph)


class TestOutlineEntriesOpeningBelowAnEntryListOnTheirPage(unittest.TestCase):
    def setUp(self) -> None:
        self.paragraphs = written_paragraphs()

    def test_an_entry_whose_destination_lies_below_the_list_opens_after_the_lists_last_entry(self) -> None:
        self.assertLess(position_of(self.paragraphs, LAST_ENTRY_AUTHOR), self.paragraphs.index(f"# {PROOFS_TITLE}"))

    def test_an_entry_whose_destination_lies_below_the_list_opens_above_the_prose_below_it(self) -> None:
        self.assertEqual([f"# {PROOFS_TITLE}", PROOF], self.paragraphs[-2:])


if __name__ == "__main__":
    unittest.main()
