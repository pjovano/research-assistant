from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path
from unittest import mock

from _support import LiveTree

LiveTree.activate()

from _extract.cache import MarkerCache
from _extract.cli import main
from _extract.console import EXIT_OK
from _extract.engine import MODE_TEXT_LAYER
from _vaults import TempVault, TextPdf

EXTRACT_DIRS = ("LIBRARY_DIR", "CORPUS_DIR")
BASENAME = "Doe - 2020 - A Work"
NOTE_TEXT = "---\ntitle: A Work\ntype: book\n---\n\n[Doe - 2020 - A Work.pdf](zotero://open-pdf/x)\n"
PAGES = 9
OUTLINE = [[1, "Introduction", 3], [1, "Chapter One", 6]]
ALL_PAGES = list(range(1, PAGES + 1))
PAGE_KIND = "Page"
TEXT_KIND = "Text"
CONTENTS_KIND = "TableOfContents"
BIBLIOGRAPHY_KIND = "Bibliography"
FOOTER_KIND = "PageFooter"
BBOX = [0.0, 0.0, 100.0, 100.0]
KINDS_BY_PAGE = {1: [TEXT_KIND], 2: [CONTENTS_KIND], 3: [TEXT_KIND], 4: [TEXT_KIND], 5: [FOOTER_KIND], 6: [],
                 7: [TEXT_KIND], 8: [BIBLIOGRAPHY_KIND], 9: [BIBLIOGRAPHY_KIND]}


def block(kind: str, file_page: int, index: int) -> dict:
    return {"block_type": kind, "html": f"<p>{kind} on page {file_page}</p>", "bbox": BBOX,
            "id": f"/page/{file_page}/{kind}/{index}"}


def engine_payload(kinds_by_page: dict[int, list[str]]) -> dict:
    pages = [{"block_type": PAGE_KIND, "children": [block(kind, page, index) for index, kind in enumerate(kinds)]}
             for page, kinds in sorted(kinds_by_page.items())]
    return {"children": pages}


class FakeEngine:
    def __init__(self, *_models_and_mode) -> None:
        pass

    @staticmethod
    def convert(_pdf_path: Path, _file_pages: list[int]) -> dict:
        return engine_payload(KINDS_BY_PAGE)


class CapturedRun:
    def __init__(self, argv: list[str]) -> None:
        self._argv = argv
        self.output = ""
        self.code = 0

    def go(self) -> "CapturedRun":
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            self.code = main(self._argv)
        self.output = output.getvalue()
        return self

    def payload(self) -> dict:
        return json.loads(self.output)


class ScopeVaultCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault(*EXTRACT_DIRS).activate()
        self.addCleanup(self.vault.discard)
        self.pdf = TextPdf(self.vault.library / f"{BASENAME}.pdf", PAGES, OUTLINE).write()
        (self.vault.corpus / f"{BASENAME}.md").write_text(NOTE_TEXT, encoding="utf-8")

    def listing(self) -> dict:
        return CapturedRun(["scope", f"{BASENAME}.pdf"]).go().payload()


class TestScopeBeforeConversion(ScopeVaultCase):
    def test_a_work_the_engine_has_not_read_lists_no_pre_labelled_runs(self) -> None:
        self.assertIsNone(self.listing()["pre_labelled"])

    def test_the_pages_to_judge_are_as_before(self) -> None:
        self.assertEqual([1, 2, 3, 6, 7, 8, 9], [page["file_page"] for page in self.listing()["pages"]])


class TestScopeAfterConversion(ScopeVaultCase):
    def setUp(self) -> None:
        super().setUp()
        MarkerCache(self.pdf, MODE_TEXT_LAYER).save(ALL_PAGES, engine_payload(KINDS_BY_PAGE))

    def test_a_contents_page_is_a_pre_labelled_run(self) -> None:
        self.assertIn({"first_page": 2, "last_page": 2, "label": CONTENTS_KIND}, self.listing()["pre_labelled"])

    def test_pages_holding_no_body_block_form_a_blank_run(self) -> None:
        self.assertIn({"first_page": 5, "last_page": 6, "label": "blank"}, self.listing()["pre_labelled"])

    def test_consecutive_bibliography_pages_form_one_run(self) -> None:
        self.assertIn({"first_page": 8, "last_page": 9, "label": BIBLIOGRAPHY_KIND}, self.listing()["pre_labelled"])

    def test_the_runs_are_listed_in_page_order(self) -> None:
        self.assertEqual([2, 5, 8], [run["first_page"] for run in self.listing()["pre_labelled"]])

    def test_the_first_and_last_page_of_every_run_join_the_pages_to_judge(self) -> None:
        self.assertEqual([1, 2, 3, 5, 6, 7, 8, 9], [page["file_page"] for page in self.listing()["pages"]])


class TestConvertFillsTheCache(ScopeVaultCase):
    def _convert(self, *flags: str) -> CapturedRun:
        with mock.patch("_extract.stage.EngineSession", contextlib.nullcontext), \
                mock.patch("_extract.build.MarkerEngine", FakeEngine):
            return CapturedRun(["convert", f"{BASENAME}.pdf", *flags]).go()

    def test_convert_reports_the_mode_and_the_pages_it_read(self) -> None:
        run = self._convert()
        self.assertEqual((EXIT_OK, MODE_TEXT_LAYER, PAGES), (run.code, run.payload()["mode"], run.payload()["pages"]))

    def test_the_scope_listing_reads_the_runs_convert_cached(self) -> None:
        self._convert()
        self.assertEqual([CONTENTS_KIND, "blank", BIBLIOGRAPHY_KIND],
                         [run["label"] for run in self.listing()["pre_labelled"]])

    def test_convert_writes_nothing_into_the_corpus_file(self) -> None:
        self._convert()
        self.assertEqual(NOTE_TEXT, (self.vault.corpus / f"{BASENAME}.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
