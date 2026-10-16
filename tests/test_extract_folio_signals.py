from __future__ import annotations

import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.blocks import Block, DocumentBlocks, PageBlocks
from _extract.build import BuildInputs, CorpusBuild
from _extract.layer import TextLayer
from _extract.pagefolios import FolioReader, folio_log
from _extract.paths import CorpusFile
from _extract.readings import WorkerReadings
from _extract.spans import ExcludedSpans
from _extract_fixtures import FakeLayer
from _pagetext.folio import LabelNormalizer
from _pagetext_fixtures import FakePredictor
from _vaults import TempVault

EXTRACT_DIRS = ("LIBRARY_DIR", "CORPUS_DIR")
BASENAME = "Doe - 2020 - A Work"
NOTE_TEXT = "---\ntitle: A Work\ntype: book\n---\n\n[Doe - 2020 - A Work.pdf](zotero://open-pdf/x)\n"
HEADER_KIND = "PageHeader"
TEXT_KIND = "Text"
HEADER_BASELINE = 40.0
BODY_BASELINE = 100.0
LEFT = 72.0
HEADER_BOX = (0.0, 28.0, 600.0, 46.0)
BODY_BOX = (0.0, 86.0, 600.0, 106.0)
BODY_TEXT = "Prose of the work on this page."
ROMAN_THEN_DECIMAL = [{"startpage": 0, "prefix": "", "style": "r", "firstpagenum": 1},
                      {"startpage": 3, "prefix": "", "style": "D", "firstpagenum": 1}]
FILE_PAGE_NUMBERING = [{"startpage": 0, "prefix": "", "style": "D", "firstpagenum": 1}]
PRINTED_HEADERS = ["Title 12", "Title 13", "Title 14", None]
GOOD_LABEL = "good"


class LabelledPdf:
    def __init__(self, path: Path, headers: list[str | None], labels: list[dict]) -> None:
        self._path = path
        self._headers = headers
        self._labels = labels

    def write(self) -> Path:
        with pymupdf.open() as document:
            for header in self._headers:
                self._page(document, header)
            document.set_page_labels(self._labels)
            document.save(self._path)
        return self._path

    @staticmethod
    def _page(document, header: str | None) -> None:
        page = document.new_page()
        if header:
            page.insert_text((LEFT, HEADER_BASELINE), header)
        page.insert_text((LEFT, BODY_BASELINE), BODY_TEXT)


def page_blocks(file_page: int, header: str | None, header_labelled: bool) -> PageBlocks:
    blocks = [Block(file_page, TEXT_KIND, f"<p>{BODY_TEXT}</p>", BODY_BOX, {}, f"/page/{file_page}/Text/1")]
    if header and header_labelled:
        blocks.insert(0,
                      Block(file_page, HEADER_KIND, f"<p>{header}</p>", HEADER_BOX, {}, f"/page/{file_page}/Header/0"))
    return PageBlocks(file_page, blocks)


class FakeModels:
    @staticmethod
    def ocr_error_model() -> FakePredictor:
        return FakePredictor(GOOD_LABEL)


class FakePlan:
    def __init__(self, headers: list[str | None], header_labelled: bool = True) -> None:
        pages = [page_blocks(number, header, header_labelled) for number, header in enumerate(headers, start=1)]
        self._blocks = DocumentBlocks(pages)
        self.models = FakeModels()
        self.mode = "text-layer"

    @staticmethod
    def reads_pixels(_file_page: int) -> bool:
        return False

    def blocks(self, _page_count: int) -> DocumentBlocks:
        return self._blocks


class LabelledPdfCase(unittest.TestCase):
    HEADERS: list[str | None] = []
    LABELS: list[dict] = []
    HEADER_LABELLED = True

    def setUp(self) -> None:
        self.vault = TempVault(*EXTRACT_DIRS).activate()
        self.addCleanup(self.vault.discard)
        self.pdf = LabelledPdf(self.vault.library / f"{BASENAME}.pdf", self.HEADERS, self.LABELS).write()
        (self.vault.corpus / f"{BASENAME}.md").write_text(NOTE_TEXT, encoding="utf-8")
        self.layer = TextLayer(self.pdf)
        self.addCleanup(self.layer.close)
        self.plan = FakePlan(self.HEADERS, self.HEADER_LABELLED)
        self.build = CorpusBuild(BuildInputs(self.pdf, CorpusFile(self.pdf), self.plan, WorkerReadings([]),
                                             ExcludedSpans.none()))

    def folios(self) -> list[str | None]:
        return list(FolioReader(self.layer).of(self.plan.blocks(len(self.HEADERS)).pages).values())


class TestLabelsWhereNoFolioPrints(LabelledPdfCase):
    HEADERS = [None] * 5
    LABELS = ROMAN_THEN_DECIMAL

    def test_a_page_printing_no_folio_takes_the_pdfs_page_label(self) -> None:
        self.assertEqual(["i", "ii", "iii", "1", "2"], self.folios())

    def test_a_roman_label_stays_roman_in_the_page_marker(self) -> None:
        self.assertIn("%% p. iii (file p. 3) %%", self.build.rendered().text)

    def test_a_decimal_label_after_the_roman_run_is_the_marker_folio(self) -> None:
        self.assertIn("%% p. 1 (file p. 4) %%", self.build.rendered().text)

    def test_labels_that_contradict_no_printed_folio_are_not_logged(self) -> None:
        self.assertEqual([], self.build.folio_log())


class TestLabelsDisagreeingWithPrintedFolios(LabelledPdfCase):
    HEADERS = PRINTED_HEADERS
    LABELS = FILE_PAGE_NUMBERING

    def test_the_printed_folio_is_kept_over_the_label(self) -> None:
        self.assertEqual(["12", "13", "14"], self.folios()[:3])

    def test_the_page_marker_carries_the_printed_folio(self) -> None:
        self.assertIn("%% p. 12 (file p. 1) %%", self.build.rendered().text)

    def test_every_disagreement_is_a_finding_naming_both_readings(self) -> None:
        self.assertEqual("file p. 1: the page label '1' disagrees with the printed folio '12'",
                         self.build.folio_log()[0])
        self.assertEqual(3, len(self.build.folio_log()))

    def test_a_contradicted_label_tree_gives_no_folio_to_a_page_printing_none(self) -> None:
        self.assertIsNone(self.folios()[3])
        self.assertIn("%% file p. 4 %%", self.build.rendered().text)


class TestEdgeLinesAsTheFallbackSignal(LabelledPdfCase):
    HEADERS = PRINTED_HEADERS
    LABELS = []
    HEADER_LABELLED = False

    def test_a_running_head_the_engine_left_unlabelled_still_yields_the_folio(self) -> None:
        self.assertEqual(["12", "13", "14", None], self.folios())


class RomanHeadLayer(FakeLayer):
    def label(self, file_page: int) -> str | None:
        return "12"


class TestSignalsFromFakeLayers(unittest.TestCase):
    def _signals(self, layer):
        page = PageBlocks(1, [Block(1, HEADER_KIND, "<p>xii</p>", HEADER_BOX, {}, "/page/1/Header/0")])
        return FolioReader(layer).signals([page])

    def test_a_roman_running_head_beside_a_decimal_label_keeps_the_head_and_logs_the_label(self) -> None:
        signals = self._signals(RomanHeadLayer())
        self.assertEqual(("xii", ["file p. 1: the page label '12' disagrees with the printed folio 'xii'"]),
                         (signals[1].folio, folio_log(signals)))

    def test_a_page_with_no_label_logs_nothing(self) -> None:
        self.assertEqual([], folio_log(self._signals(FakeLayer())))


class TestLabelNormalizer(unittest.TestCase):
    def test_a_page_prefix_is_stripped(self) -> None:
        self.assertEqual("12", LabelNormalizer().normalize("p. 12"))

    def test_a_word_opening_with_p_is_kept_whole(self) -> None:
        self.assertEqual("Plate 3", LabelNormalizer().normalize("Plate 3"))

    def test_a_prefixed_folio_is_kept_as_printed(self) -> None:
        self.assertEqual("A-3", LabelNormalizer().normalize("A-3"))


if __name__ == "__main__":
    unittest.main()
