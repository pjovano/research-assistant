from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.elements import Paragraph, Verbatim
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

FONT_SIZE = 10.0
LEFT = 72.0
LABEL_COLUMN_LEFT = 200.0
FIRST_BASELINE = 100.0
LINE_PITCH = 14.0
BLOCK_RIGHT = 500.0
LEAD_IN = "We shall show that from the premisses"
PREMISSES = (("(1)", "All P are M,"), ("(2)", "No S is M,"))
CONCLUSION = "the conclusion follows."


def _draw(page, origin: tuple[float, float], text: str) -> None:
    page.insert_text(origin, text, fontsize=FONT_SIZE, fontname="helv")


def _write_page(path: Path) -> Path:
    with pymupdf.open() as document:
        page = document.new_page()
        _draw(page, (LEFT, FIRST_BASELINE), LEAD_IN)
        for row, (label, premiss) in enumerate(PREMISSES, start=1):
            _draw(page, (LEFT, FIRST_BASELINE + row * LINE_PITCH), label)
            _draw(page, (LABEL_COLUMN_LEFT, FIRST_BASELINE + row * LINE_PITCH), premiss)
        _draw(page, (LEFT, FIRST_BASELINE + (len(PREMISSES) + 1) * LINE_PITCH), CONCLUSION)
        document.save(path)
    return path


def _engine_block() -> Block:
    rows = "".join(f"<tr><td>{label}</td><td>{premiss}</td></tr>" for label, premiss in PREMISSES)
    html = f"<p>{LEAD_IN}</p><table border=\"0\">{rows}</table><p>{CONCLUSION}</p>"
    bottom = FIRST_BASELINE + (len(PREMISSES) + 2) * LINE_PITCH
    return Block(1, TEXT_KIND, html, (LEFT, FIRST_BASELINE - LINE_PITCH, BLOCK_RIGHT, bottom), {}, "/page/1/Text/0")


class TestProseSetAroundATableInOneEngineBlock(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(_write_page(Path(directory.name) / "premisses.pdf"))
        self.addCleanup(layer.close)
        blocks = DocumentBlocks([PageBlocks(1, [_engine_block()])])
        inputs = StructureInputs(blocks, [], WorkerReadings.none(), keep_everything())
        structure = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)
        self._written = [element for element in structure.elements() if isinstance(element, (Paragraph, Verbatim))]

    def test_the_prose_before_the_table_opens_the_block(self) -> None:
        self.assertEqual(Paragraph(LEAD_IN, False, 1), self._written[0])

    def test_the_table_follows_the_prose_before_it(self) -> None:
        self.assertEqual("| (1) | All P are M, |", self._written[1].text.splitlines()[0])

    def test_the_prose_after_the_table_closes_the_block(self) -> None:
        self.assertEqual(CONCLUSION, self._written[2].text)


if __name__ == "__main__":
    unittest.main()
