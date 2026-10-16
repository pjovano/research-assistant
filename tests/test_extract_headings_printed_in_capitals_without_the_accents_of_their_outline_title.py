from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.elements import Heading, Paragraph
from _extract.headings import shape_of
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.outline import Outline
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

OUTLINE_TITLE = "§ 1. Au-delà des catégories"
PRINTED_TITLE = "§ 1. AU-DELA DES CATEGORIES"
CONTINUED = "faut penser ici bien sur a Mach, mais on peut aussi songer a James."
OPENING = "L'histoire des categories d'Aristote a Kant est celle de leur detachement."
LEFT = 72.0
RIGHT = 500.0
BODY_SIZE = 10.0
TITLE_SIZE = 12.0
FIRST_BASELINE = 90.0
LINE_PITCH = 40.0
LINE_HALF_HEIGHT = 6.0
LINES = ((TEXT_KIND, CONTINUED, BODY_SIZE), (HEADING_KIND, PRINTED_TITLE, TITLE_SIZE), (TEXT_KIND, OPENING, BODY_SIZE))


class CapitalHeadingPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            for row, (_kind, text, size) in enumerate(LINES):
                page.insert_text((LEFT, _baseline(row)), text, fontsize=size)
            document.set_toc([[1, OUTLINE_TITLE, 1]])
            document.save(self._path)
        return self._path


def _baseline(row: int) -> float:
    return FIRST_BASELINE + row * LINE_PITCH


def document_blocks() -> DocumentBlocks:
    blocks = []
    for row, (kind, text, size) in enumerate(LINES):
        box = (LEFT, _baseline(row) - size - LINE_HALF_HEIGHT, RIGHT, _baseline(row) + LINE_HALF_HEIGHT)
        tag = "h2" if kind == HEADING_KIND else "p"
        blocks.append(Block(1, kind, f"<{tag}>{text}</{tag}>", box, {}, f"/page/1/{kind}/{row}"))
    return DocumentBlocks([PageBlocks(1, blocks)])


class TestHeadingsPrintedInCapitalsWithoutTheAccentsOfTheirOutlineTitle(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def _written(self) -> list[tuple[str, str]]:
        pdf_path = CapitalHeadingPdf(self._directory / "capitals.pdf").write()
        layer = TextLayer(pdf_path)
        self.addCleanup(layer.close)
        inputs = StructureInputs(document_blocks(), Outline(pdf_path).headings(), WorkerReadings.none(),
                                 keep_everything())
        work = WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts())
        return [(type(element).__name__, element.title if isinstance(element, Heading) else element.text)
                for element in NoteStructure(work, inputs).elements() if isinstance(element, (Heading, Paragraph))]

    def test_an_unaccented_capital_title_shapes_as_its_accented_outline_title(self) -> None:
        self.assertEqual(shape_of(OUTLINE_TITLE), shape_of(PRINTED_TITLE))

    def test_the_outline_heading_opens_once_where_the_capital_title_prints(self) -> None:
        expected = [(Paragraph.__name__, CONTINUED), (Heading.__name__, OUTLINE_TITLE), (Paragraph.__name__, OPENING)]
        self.assertEqual(expected, self._written())


if __name__ == "__main__":
    unittest.main()
