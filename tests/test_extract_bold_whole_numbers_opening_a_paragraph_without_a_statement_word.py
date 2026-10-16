from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.elements import Heading, Paragraph
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

BODY_FONT = "helv"
BOLD_FONT = "hebo"
DISPLAY_SIZE = 19.0
BODY_SIZE = 12.0
LEFT = 60.0
RIGHT = 560.0
BASELINE = 170.0
LINE_HALF_HEIGHT = 8.0
CHAPTER_NUMERAL = "12"
LABELLED_STATEMENT = "Theorem 3."
DOTTED_STATEMENT = "2.3."
PROSE = " It is clear then that in the first figure all problems are proved per impossibile."


class OpeningNumeralPdf:
    def __init__(self, path: Path, opening: str, size: float) -> None:
        self._path = path
        self._opening = opening
        self._size = size

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_text((LEFT, BASELINE), self._opening, fontsize=self._size, fontname=BOLD_FONT)
            prose_left = LEFT + pymupdf.get_text_length(self._opening, BOLD_FONT, self._size)
            page.insert_text((prose_left, BASELINE), PROSE, fontsize=BODY_SIZE, fontname=BODY_FONT)
            document.save(self._path)
        return self._path

    def blocks(self) -> DocumentBlocks:
        box = (LEFT - 1, BASELINE - self._size - LINE_HALF_HEIGHT, RIGHT, BASELINE + LINE_HALF_HEIGHT)
        block = Block(1, TEXT_KIND, f"<p><b>{self._opening}</b>{PROSE}</p>", box, {}, "/page/1/Text/0")
        return DocumentBlocks([PageBlocks(1, [block])])


class TestBoldWholeNumbersOpeningAParagraphWithoutAStatementWord(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._directory = Path(directory.name)

    def _written(self, opening: str, size: float) -> list[tuple[str, str]]:
        pdf = OpeningNumeralPdf(self._directory / "numeral.pdf", opening, size)
        layer = TextLayer(pdf.write())
        self.addCleanup(layer.close)
        inputs = StructureInputs(pdf.blocks(), [], WorkerReadings.none(), keep_everything())
        elements = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs).elements()
        return [(type(element).__name__, element.title if isinstance(element, Heading) else element.text)
                for element in elements if isinstance(element, (Heading, Paragraph))]

    def test_an_enlarged_bold_numeral_opening_a_paragraph_stays_in_the_paragraph(self) -> None:
        written = self._written(CHAPTER_NUMERAL, DISPLAY_SIZE)
        self.assertEqual([Paragraph.__name__], [kind for kind, _text in written])

    def test_a_bold_label_naming_a_statement_opens_a_heading(self) -> None:
        written = self._written(LABELLED_STATEMENT, BODY_SIZE)
        self.assertEqual((Heading.__name__, "Theorem 3"), written[0])

    def test_a_bold_dotted_number_numbering_a_statement_opens_a_heading(self) -> None:
        written = self._written(DOTTED_STATEMENT, BODY_SIZE)
        self.assertEqual((Heading.__name__, "2.3"), written[0])


if __name__ == "__main__":
    unittest.main()
