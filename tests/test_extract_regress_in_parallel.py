from __future__ import annotations

import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import pymupdf

from _extract.build import ConversionNotCached, ConversionOptions, ConversionPlan, DoubtfulPagesRemain
from _extract.cache import MarkerCache
from _extract.checks import PageVerdict
from _extract.engine import MODE_TEXT_LAYER
from _extract.paths import CorpusFile
from _extract.records import ExtractionRecord, ExtractionRecords
from _extract.regression import STATE_CHANGED, STATE_DOUBTFUL, STATE_UNCHANGED, RegressionCheck
from _extract.request import ExtractionRequest
from _vaults import TempVault, TextPdf

EXTRACT_DIRS = ("LIBRARY_DIR", "CORPUS_DIR")
FRONTMATTER = "---\ntitle: A Work\n---\n"
LINK_LINE = "[{basename}.pdf](zotero://open-pdf/x)"
REVIEWED = "2026-09-30"
DOUBTFUL_PAGE_COUNT = 1
CHANGED_LINE = "A line the accepted body carries and the rebuild does not."
PARALLEL_JOBS = 3
WORKS = (
    ("Ames - 2001 - First", 2, STATE_UNCHANGED),
    ("Bede - 2002 - Second", 3, STATE_CHANGED),
    ("Cole - 2003 - Third", DOUBTFUL_PAGE_COUNT, STATE_DOUBTFUL),
    ("Dunn - 2004 - Fourth", 4, STATE_UNCHANGED),
    ("Eads - 2005 - Fifth", 2, STATE_CHANGED),
)


class LayerRendered:
    def __init__(self, text: str) -> None:
        self.text = text


class LayerBuild:
    def __init__(self, pdf_path: Path) -> None:
        self._pdf_path = pdf_path

    def rendered(self) -> LayerRendered:
        pages = self._pages()
        if len(pages) == DOUBTFUL_PAGE_COUNT:
            raise DoubtfulPagesRemain([PageVerdict(DOUBTFUL_PAGE_COUNT, "doubtful", "length", "")])
        return LayerRendered("\n\n".join(f"%% file p. {number} %%\n{text}" for number, text in enumerate(pages, 1)))

    def _pages(self) -> list[str]:
        with pymupdf.open(self._pdf_path) as document:
            return [page.get_text().strip() for page in document]


class LayerBuilder:
    def __call__(self, pdf_path: Path, _note: CorpusFile, _request: ExtractionRequest) -> LayerBuild:
        return LayerBuild(pdf_path)


class UncachedBuilder(LayerBuilder):
    def __init__(self, uncached: Path) -> None:
        self._uncached = uncached

    def __call__(self, pdf_path: Path, note: CorpusFile, request: ExtractionRequest) -> LayerBuild:
        if request.cache_only and pdf_path == self._uncached:
            raise ConversionNotCached(pdf_path.name)
        return super().__call__(pdf_path, note, request)


class ReviewedLibrary:
    def __init__(self, library: Path, corpus: Path) -> None:
        self._library = library
        self._corpus = corpus

    def filed(self) -> list[Path]:
        return [self._reviewed_work(basename, pages, state) for basename, pages, state in WORKS]

    def _reviewed_work(self, basename: str, pages: int, state: str) -> Path:
        pdf_path = TextPdf(self._library / f"{basename}.pdf", pages).write()
        (self._corpus / f"{basename}.md").write_text(f"{FRONTMATTER}\n{LINK_LINE.format(basename=basename)}\n",
                                                    encoding="utf-8")
        CorpusFile(pdf_path).write(self._accepted_body(pdf_path, state), {})
        ExtractionRecords().write(basename, ExtractionRecord(ExtractionRequest(()), None, REVIEWED))
        return pdf_path

    @staticmethod
    def _accepted_body(pdf_path: Path, state: str) -> str:
        if state == STATE_DOUBTFUL:
            return CHANGED_LINE
        rebuilt = LayerBuild(pdf_path).rendered().text
        return f"{rebuilt}\n\n{CHANGED_LINE}" if state == STATE_CHANGED else rebuilt


class ParallelRegressionCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault(*EXTRACT_DIRS).activate()
        self.addCleanup(self.vault.discard)
        self.pdfs = ReviewedLibrary(self.vault.library, self.vault.corpus).filed()

    @staticmethod
    def works_of(report: list[dict]) -> list[str]:
        return [work["work"] for work in report]


class TestAParallelRunReportsWhatASerialRunReports(ParallelRegressionCase):
    def test_the_reports_are_equal(self) -> None:
        serial = RegressionCheck(LayerBuilder(), 1).run(self.pdfs)
        self.assertEqual(serial, RegressionCheck(LayerBuilder(), PARALLEL_JOBS).run(self.pdfs))

    def test_each_work_reaches_its_state(self) -> None:
        report = RegressionCheck(LayerBuilder(), PARALLEL_JOBS).run(self.pdfs)
        self.assertEqual([state for _basename, _pages, state in WORKS], [work["state"] for work in report])

    def test_each_changed_work_writes_its_own_diff(self) -> None:
        report = RegressionCheck(LayerBuilder(), PARALLEL_JOBS).run(self.pdfs)
        changed = [work for work in report if work["state"] == STATE_CHANGED]
        self.assertEqual([f"{work['work']}.diff" for work in changed], [Path(work["diff"]).name for work in changed])

    def test_each_diff_holds_its_own_works_change(self) -> None:
        report = RegressionCheck(LayerBuilder(), PARALLEL_JOBS).run(self.pdfs)
        diffs = [Path(work["diff"]).read_text(encoding="utf-8") for work in report if work["state"] == STATE_CHANGED]
        self.assertTrue(all(f"-{CHANGED_LINE}" in diff for diff in diffs))


class TestTheReportKeepsTheOrderOfTheWorksGiven(ParallelRegressionCase):
    def test_the_order_given_is_the_order_reported(self) -> None:
        report = RegressionCheck(LayerBuilder(), PARALLEL_JOBS).run(self.pdfs)
        self.assertEqual([pdf.stem for pdf in self.pdfs], self.works_of(report))

    def test_a_reversed_order_given_is_reported_reversed(self) -> None:
        reversed_pdfs = list(reversed(self.pdfs))
        report = RegressionCheck(LayerBuilder(), PARALLEL_JOBS).run(reversed_pdfs)
        self.assertEqual([pdf.stem for pdf in reversed_pdfs], self.works_of(report))


class TestAWorkTheCacheDoesNotHoldIsRebuiltAfterThePool(ParallelRegressionCase):
    def test_it_keeps_its_place_and_its_state(self) -> None:
        uncached = self.pdfs[1]
        report = RegressionCheck(UncachedBuilder(uncached), PARALLEL_JOBS).run(self.pdfs)
        self.assertEqual(RegressionCheck(LayerBuilder(), 1).run(self.pdfs), report)


class RefusingModels:
    def ocr_error_model(self):
        raise AssertionError("a cache-only plan loads no model")


class TestACacheOnlyPlanNeverConverts(unittest.TestCase):
    PAGES = 2

    def setUp(self) -> None:
        self.vault = TempVault("LIBRARY_DIR").activate()
        self.addCleanup(self.vault.discard)
        self.pdf = TextPdf(self.vault.library / "Doe - 2020 - A Work.pdf", self.PAGES).write()
        self.plan = ConversionPlan(self.pdf, ConversionOptions(cache_only=True), RefusingModels())

    def test_an_uncached_conversion_is_refused(self) -> None:
        with self.assertRaises(ConversionNotCached):
            self.plan.blocks(self.PAGES)

    def test_a_cached_conversion_is_read(self) -> None:
        all_pages = list(range(1, self.PAGES + 1))
        MarkerCache(self.pdf, MODE_TEXT_LAYER).save(all_pages, {"children": []})
        self.assertEqual([], self.plan.blocks(self.PAGES).pages)


if __name__ == "__main__":
    unittest.main()
