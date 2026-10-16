from __future__ import annotations

import unittest

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.blocks import TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.build import BuildInputs, CorpusBuild
from _extract.checks import REASON_WIDE_LETTER_IN_NOTATION
from _extract.paths import CorpusFile
from _extract.readings import WorkerReadings
from _extract.spans import ExcludedSpans
from _extract_fixtures import PROSE
from _pagetext_fixtures import FakePredictor
from _vaults import TempVault

BASENAME = "Doe - 2020 - A Scanned Treatise on Implication"
NOTE_TEXT = f"---\ntitle: A Scanned Treatise on Implication\ntype: book\n---\n\n[{BASENAME}.pdf](zotero://open-pdf/x)\n"
FILE_PAGE = 1
FONT = "tiro"
FONT_SIZE = 10.0
INVISIBLE = 3
SCAN_GREY = 230
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
FIRST_BASELINE = 100.0
LINE_PITCH = 14.0
LAYER_LINE_CHARS = 60
BLOCK_TOP = 80.0
BLOCK_BOTTOM = 600.0
GARBLED_FORMULA = "Xi -U X, (in S) =Df LrXi C LrXj."
SENTENCE = "We say that one sentence L-implies another, written"
IDEOGRAPH_FORMULA = "<math>\\mathcal{T}_i 脈 \\mathcal{T}_j</math>"
FULL_WIDTH_FORMULA = "<math>\\mathcal{T}_i Ｔ \\mathcal{T}_j</math>"
OPERATOR_FORMULA = "<math>\\mathcal{T}_i \\Rightarrow \\mathcal{T}_j</math>"
PROSE_IDEOGRAPH = "the character 道 names the way, and"


class FakeModels:
    @staticmethod
    def ocr_error_model() -> FakePredictor:
        return FakePredictor("good")


class PixelPlan:
    def __init__(self, engine_html: str) -> None:
        block = Block(FILE_PAGE, TEXT_KIND, f"<p>{engine_html}</p>", (LEFT, BLOCK_TOP, RIGHT, BLOCK_BOTTOM), {},
                      f"/page/{FILE_PAGE}/{TEXT_KIND}/0")
        self._blocks = DocumentBlocks([PageBlocks(FILE_PAGE, [block])])
        self.models = FakeModels()
        self.mode = "forced-ocr"

    @staticmethod
    def reads_pixels(_file_page: int) -> bool:
        return True

    def blocks(self, _page_count: int) -> DocumentBlocks:
        return self._blocks


class ScannedPage:
    def __init__(self, layer_text: str) -> None:
        self._layer_lines = [layer_text[start:start + LAYER_LINE_CHARS]
                             for start in range(0, len(layer_text), LAYER_LINE_CHARS)]

    def write(self, path) -> None:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            scan = pymupdf.Pixmap(pymupdf.csGRAY, pymupdf.IRect(0, 0, 60, 80), False)
            scan.set_rect(scan.irect, (SCAN_GREY,))
            page.insert_image(page.rect, pixmap=scan, keep_proportion=False)
            for row, line in enumerate(self._layer_lines):
                page.insert_text((LEFT, FIRST_BASELINE + row * LINE_PITCH), line, fontsize=FONT_SIZE,
                                 fontname=FONT, render_mode=INVISIBLE)
            document.save(path)


class TestSymbolsTheEngineReadsFromPixelsAsAWideLetterInsideANotationSpan(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("LIBRARY_DIR", "CORPUS_DIR").activate()
        self.addCleanup(self.vault.discard)
        self.pdf = self.vault.library / f"{BASENAME}.pdf"
        ScannedPage(f"{PROSE}{SENTENCE} {GARBLED_FORMULA} {PROSE}").write(self.pdf)
        (self.vault.corpus / f"{BASENAME}.md").write_text(NOTE_TEXT, encoding="utf-8")

    def _verdict(self, engine_html: str):
        build = CorpusBuild(BuildInputs(self.pdf, CorpusFile(self.pdf), PixelPlan(engine_html), WorkerReadings([]),
                                        ExcludedSpans([])))
        [verdict] = build.verdicts()
        return verdict

    def test_a_page_whose_notation_span_holds_an_ideograph_is_doubtful(self) -> None:
        verdict = self._verdict(f"{PROSE}{SENTENCE} {IDEOGRAPH_FORMULA}. {PROSE}")
        self.assertEqual((True, True), (verdict.is_doubtful, verdict.reason.startswith(REASON_WIDE_LETTER_IN_NOTATION)))

    def test_a_page_whose_notation_span_holds_a_full_width_letter_is_doubtful(self) -> None:
        verdict = self._verdict(f"{PROSE}{SENTENCE} {FULL_WIDTH_FORMULA}. {PROSE}")
        self.assertEqual((True, True), (verdict.is_doubtful, verdict.reason.startswith(REASON_WIDE_LETTER_IN_NOTATION)))

    def test_a_page_whose_notation_span_holds_an_operator_is_kept(self) -> None:
        self.assertFalse(self._verdict(f"{PROSE}{SENTENCE} {OPERATOR_FORMULA}. {PROSE}").is_doubtful)

    def test_a_page_whose_prose_writes_an_ideograph_outside_its_notation_is_kept(self) -> None:
        self.assertFalse(self._verdict(f"{PROSE}{PROSE_IDEOGRAPH} {SENTENCE} {OPERATOR_FORMULA}. {PROSE}").is_doubtful)


if __name__ == "__main__":
    unittest.main()
