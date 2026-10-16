from __future__ import annotations

import unittest

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.blocks import DocumentBlocks, PageBlocks
from _extract.build import BuildInputs, CorpusBuild
from _extract.checks import REASON_EMPTY_PIXELS
from _extract.paths import CorpusFile
from _extract.readings import WorkerReadings
from _extract.spans import ExcludedSpan, ExcludedSpans, PagePlace
from _pagetext_fixtures import FakePredictor
from _vaults import TempVault

BASENAME = "Doe - 2020 - A Scanned Work"
NOTE_TEXT = f"---\ntitle: A Scanned Work\ntype: book\n---\n\n[{BASENAME}.pdf](zotero://open-pdf/x)\n"
PAGES = 3
KEPT_BLANK = 1
EXCLUDED_BLANK = 2


class FakeModels:
    @staticmethod
    def ocr_error_model() -> FakePredictor:
        return FakePredictor("good")


class PixelPlan:
    def __init__(self) -> None:
        self._blocks = DocumentBlocks([PageBlocks(number, []) for number in range(1, PAGES + 1)])
        self.models = FakeModels()
        self.mode = "forced-ocr"

    @staticmethod
    def reads_pixels(_file_page: int) -> bool:
        return True

    def blocks(self, _page_count: int) -> DocumentBlocks:
        return self._blocks


class TestPagesReadFromPixelsIntoNoText(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("LIBRARY_DIR", "CORPUS_DIR").activate()
        self.addCleanup(self.vault.discard)
        pdf = self.vault.library / f"{BASENAME}.pdf"
        with pymupdf.open() as document:
            for _number in range(PAGES):
                document.new_page()
            document.save(pdf)
        (self.vault.corpus / f"{BASENAME}.md").write_text(NOTE_TEXT, encoding="utf-8")
        spans = ExcludedSpans([ExcludedSpan(PagePlace(EXCLUDED_BLANK), PagePlace(EXCLUDED_BLANK + 1))])
        build = CorpusBuild(BuildInputs(pdf, CorpusFile(pdf), PixelPlan(), WorkerReadings([]), spans))
        self.verdicts = {verdict.file_page: verdict for verdict in build.verdicts()}

    def test_a_kept_page_whose_pixels_gave_no_text_is_doubtful(self) -> None:
        verdict = self.verdicts[KEPT_BLANK]
        self.assertEqual((True, REASON_EMPTY_PIXELS), (verdict.is_doubtful, verdict.reason))

    def test_a_page_the_scope_excludes_whole_is_kept_though_its_pixels_gave_no_text(self) -> None:
        self.assertFalse(self.verdicts[EXCLUDED_BLANK].is_doubtful)


if __name__ == "__main__":
    unittest.main()
