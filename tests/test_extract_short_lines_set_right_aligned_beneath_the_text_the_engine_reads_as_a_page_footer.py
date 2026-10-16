from __future__ import annotations

import shutil
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.blocks import FOOTER_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.furniture import WorkFurniture
from _extract.layer import TextLayer

QUOTATION = ["It is a natural supposition that before philosophy gets to the business",
             "itself it would first be necessary to come to an agreement about cognition,",
             "which is considered as the instrument with which one takes control."]
CITATION = "(p. 73)"
FOLIO = "45"
NOTE = "31. Alternatively: at each of the two turnings."
FILE_PAGE = 1
FONT = "helv"
TEXT_SIZE = 10.0
SMALL_SIZE = 6.0
LEFT = 75.0
RIGHT = 440.0
FIRST_BASELINE = 100.0
LINE_PITCH = 12.5
NEXT_LINE = len(QUOTATION)
QUOTATION_RIGHT = LEFT + max(pymupdf.get_text_length(line, fontname=FONT, fontsize=TEXT_SIZE) for line in QUOTATION)
TWO_LINES_DOWN = NEXT_LINE + 2


@dataclass(frozen=True)
class FooterLine:
    text: str
    row: int = NEXT_LINE
    size: float = TEXT_SIZE
    opens_at_the_margin: bool = False

    @property
    def baseline(self) -> float:
        return _baseline(self.row)

    @property
    def left(self) -> float:
        if self.opens_at_the_margin:
            return LEFT
        return QUOTATION_RIGHT - pymupdf.get_text_length(self.text, fontname=FONT, fontsize=self.size)


def _baseline(row: int) -> float:
    return FIRST_BASELINE + row * LINE_PITCH


class QuotationPagePdf:
    def __init__(self, directory: Path) -> None:
        self._path = directory / "quotation.pdf"

    def write(self, footer: FooterLine) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            for row, line in enumerate(QUOTATION):
                page.insert_text((LEFT, _baseline(row)), line, fontsize=TEXT_SIZE, fontname=FONT)
            page.insert_text((footer.left, footer.baseline), footer.text, fontsize=footer.size, fontname=FONT)
            document.save(self._path)
        return self._path


def engine_reading(footer: FooterLine) -> DocumentBlocks:
    quotation_box = (LEFT - 2.0, _baseline(0) - TEXT_SIZE, RIGHT, _baseline(NEXT_LINE - 1) + 3.0)
    footer_box = (footer.left - 2.0, footer.baseline - footer.size, RIGHT + 2.0, footer.baseline + 3.0)
    return DocumentBlocks([PageBlocks(FILE_PAGE, [
        Block(FILE_PAGE, TEXT_KIND, f"<p>{' '.join(QUOTATION)}</p>", quotation_box, {}, "/page/1/quotation"),
        Block(FILE_PAGE, FOOTER_KIND, f"<p>{footer.text}</p>", footer_box, {}, "/page/1/footer"),
    ])])


class TestShortLinesSetRightAlignedBeneathTheTextTheEngineReadsAsAPageFooter(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def _footer_kind(self, footer: FooterLine) -> str:
        layer = TextLayer(QuotationPagePdf(self._directory).write(footer))
        self.addCleanup(layer.close)
        refiled = WorkFurniture(layer).refiled(engine_reading(footer))
        return next(block.kind for block in refiled.pages[0].blocks if block.plain_text == footer.text)

    def test_a_citation_on_the_line_beneath_a_quotation_in_its_type_is_text(self) -> None:
        self.assertEqual(TEXT_KIND, self._footer_kind(FooterLine(CITATION)))

    def test_a_citation_set_two_lines_beneath_the_quotation_stays_furniture(self) -> None:
        self.assertEqual(FOOTER_KIND, self._footer_kind(FooterLine(CITATION, TWO_LINES_DOWN)))

    def test_a_line_set_smaller_than_the_quotation_stays_furniture(self) -> None:
        self.assertEqual(FOOTER_KIND, self._footer_kind(FooterLine(CITATION, size=SMALL_SIZE)))

    def test_a_line_opening_at_the_quotations_margin_stays_furniture(self) -> None:
        self.assertEqual(FOOTER_KIND, self._footer_kind(FooterLine(NOTE, opens_at_the_margin=True)))

    def test_a_bare_folio_on_the_line_beneath_the_text_stays_furniture(self) -> None:
        self.assertEqual(FOOTER_KIND, self._footer_kind(FooterLine(FOLIO)))


if __name__ == "__main__":
    unittest.main()
