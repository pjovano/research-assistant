from __future__ import annotations

import tempfile
import unittest
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
LABEL_FONT = "helv"
ARROW_FONT = "cour"
ARROW_FONT_NAME = "Courier"
ARROW_CODE = "|"
ZERO_WIDTH_SPACE = "​"
TYPE_SIZE = 10.0
LEFT = 40.0
RIGHT = 360.0
ARROW_COLUMNS = (60.0, 160.0, 260.0)
PITCH = 12.0
HALF_LINE = 6.0
PAGE_WIDTH = 400.0
PAGE_HEIGHT = 600.0
ABOVE = ("The structure of the subject took the form of a", "bifurcating scheme of oppositions, set out below:")
BELOW = ("This last scheme served as the basis of teaching", "for many centuries after it was first proposed.")
LABELS = ("Knowledge", "divided into", "The finite The infinite")
ABOVE_BASELINE = 80.0
DIAGRAM_BASELINE = 140.0
BELOW_BASELINE = 320.0
_CMAP = ("/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CMapName /Arrows def "
         "1 begincodespacerange <00> <FF> endcodespacerange 1 beginbfchar <{code:02X}> <{char:04X}> endbfchar "
         "endcmap CMapName currentdict /CMap defineresource pop end end")


class DiagramBetweenArrowsPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            self._draw_text(page, ABOVE_BASELINE, ABOVE)
            self._draw_diagram(page)
            self._draw_text(page, BELOW_BASELINE, BELOW)
            self._map_arrows_to_zero_width_spaces(document, page)
            document.save(self._path)
        return self._path

    def blocks(self) -> DocumentBlocks:
        return DocumentBlocks([PageBlocks(1, [_text_block(ABOVE_BASELINE, ABOVE), self._diagram_block(),
                                              _text_block(BELOW_BASELINE, BELOW)])])

    @staticmethod
    def _draw_text(page, baseline: float, lines: tuple[str, ...]) -> None:
        for row, line in enumerate(lines):
            page.insert_text((LEFT, baseline + row * PITCH), line, fontsize=TYPE_SIZE, fontname=LABEL_FONT)

    def _draw_diagram(self, page) -> None:
        for index, label in enumerate(LABELS):
            arrow_baseline = DIAGRAM_BASELINE + 2 * index * PITCH
            for column in ARROW_COLUMNS:
                page.insert_text((column, arrow_baseline), ARROW_CODE, fontsize=TYPE_SIZE, fontname=ARROW_FONT)
            page.insert_text((LEFT, arrow_baseline + PITCH), label, fontsize=TYPE_SIZE, fontname=LABEL_FONT)

    @staticmethod
    def _map_arrows_to_zero_width_spaces(document, page) -> None:
        font_xref = next(font[0] for font in page.get_fonts() if font[3] == ARROW_FONT_NAME)
        cmap_xref = document.get_new_xref()
        document.update_object(cmap_xref, "<<>>")
        document.update_stream(cmap_xref, _CMAP.format(code=ord(ARROW_CODE), char=ord(ZERO_WIDTH_SPACE)).encode())
        document.xref_set_key(font_xref, "ToUnicode", f"{cmap_xref} 0 R")

    @staticmethod
    def _diagram_block() -> Block:
        bottom = DIAGRAM_BASELINE + (2 * len(LABELS) - 1) * PITCH + HALF_LINE
        box = (LEFT, DIAGRAM_BASELINE - TYPE_SIZE - HALF_LINE, RIGHT, bottom)
        return Block(1, DIAGRAM_KIND, "", box, {}, "/page/1/Diagram/0")


def _text_block(baseline: float, lines: tuple[str, ...]) -> Block:
    box = (LEFT, baseline - TYPE_SIZE - HALF_LINE, RIGHT, baseline + (len(lines) - 1) * PITCH + HALF_LINE)
    return Block(1, TEXT_KIND, f"<p>{' '.join(lines)}</p>", box, {}, f"/page/1/Text/{baseline}")


class TestDiagramLabelsBetweenArrowsTheLayerMapsToZeroWidthCharacters(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        pdf = DiagramBetweenArrowsPdf(Path(directory.name) / "diagram.pdf")
        layer = TextLayer(pdf.write())
        self.addCleanup(layer.close)
        inputs = StructureInputs(pdf.blocks(), [], WorkerReadings.none(), keep_everything())
        structure = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)
        self.written = NoteWriter().render(structure.elements(), structure.definitions()).text

    def test_labels_between_zero_width_arrows_are_written_one_line_each(self) -> None:
        self.assertIn("\n".join(LABELS), self.written)

    def test_zero_width_arrows_write_no_character(self) -> None:
        self.assertNotIn(ZERO_WIDTH_SPACE, self.written)


if __name__ == "__main__":
    unittest.main()
