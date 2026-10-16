from __future__ import annotations

import contextlib
import io
import json
import unittest

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.cache import MarkerCache
from _extract.cli import main
from _extract.console import EXIT_OK, EXIT_USAGE
from _extract.engine import MODE_TEXT_LAYER
from _extract.pagelabels import LabelRanges, roman_value
from _vaults import TempVault, TextPdf

EXTRACT_DIRS = ("LIBRARY_DIR", "CORPUS_DIR")
BASENAME = "Doe - 2020 - A Work"
LINK_LINE = "[Doe - 2020 - A Work.pdf](zotero://open-pdf/x)"
FRONTMATTER = "---\ntitle: A Work\ntype: book\n---\n"
UNCITABLE_FRONTMATTER = "---\ntitle: A Work\ntype: book\nuncitable: the held copy is a preprint\n---\n"
PAGES = 5
BODY = ("%% p. i (file p. 1) %%\nFront matter.\n\n%% p. ii (file p. 2) %%\nMore front matter.\n\n"
        "%% p. 1 (file p. 3) %%\nThe text.\n\n%% p. 2 (file p. 4) %%\nMore text.\n")
ROMAN_THEN_DECIMAL_THEN_NONE = [{"startpage": 0, "prefix": "", "firstpagenum": 1, "style": "r"},
                                {"startpage": 2, "prefix": "", "firstpagenum": 1, "style": "D"},
                                {"startpage": 4, "prefix": "", "firstpagenum": 1}]
ALL_PAGES = list(range(1, PAGES + 1))
CACHED_PAYLOAD = {"children": []}


class CapturedRun:
    def __init__(self, argv: list[str]) -> None:
        self._argv = argv
        self.output = ""
        self.errors = ""
        self.code = 0

    def go(self) -> "CapturedRun":
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            self.code = main(self._argv)
        self.output, self.errors = output.getvalue(), errors.getvalue()
        return self

    def payload(self) -> dict:
        return json.loads(self.output)


class LabelVaultCase(unittest.TestCase):
    NOTE_TEXT = f"{FRONTMATTER}\n{LINK_LINE}\n\n{BODY}"

    def setUp(self) -> None:
        self.vault = TempVault(*EXTRACT_DIRS).activate()
        self.addCleanup(self.vault.discard)
        self.pdf = TextPdf(self.vault.library / f"{BASENAME}.pdf", PAGES).write()
        (self.vault.corpus / f"{BASENAME}.md").write_text(self.NOTE_TEXT, encoding="utf-8")

    def labels_in_pdf(self) -> list[str]:
        with pymupdf.open(self.pdf) as document:
            return [page.get_label() for page in document]

    def ranges_in_pdf(self) -> list[dict]:
        with pymupdf.open(self.pdf) as document:
            return document.get_page_labels()


class TestTheReadOnlyForm(LabelVaultCase):
    def setUp(self) -> None:
        super().setUp()
        self.run = CapturedRun(["labels", f"{BASENAME}.pdf"]).go()

    def test_the_plan_carries_one_range_per_run_of_consecutive_folios(self) -> None:
        planned = [(found["startpage"], found["style"], found["firstpagenum"])
                   for found in self.run.payload()["planned"]]
        self.assertEqual([(0, "r", 1), (2, "D", 1), (4, "", 0)], planned)

    def test_the_plan_counts_the_labelled_pages(self) -> None:
        self.assertEqual(4, self.run.payload()["labelled_pages"])

    def test_nothing_is_written(self) -> None:
        self.assertEqual(([""] * PAGES, False, None),
                         (self.labels_in_pdf(), self.run.payload()["written"], self.run.payload()["read_back"]))


class TestTheWritingForm(LabelVaultCase):
    def setUp(self) -> None:
        super().setUp()
        MarkerCache(self.pdf, MODE_TEXT_LAYER).save(ALL_PAGES, CACHED_PAYLOAD)
        self.run = CapturedRun(["labels", f"{BASENAME}.pdf", "--apply"]).go()

    def test_the_pdf_shows_each_page_marker_folio_as_its_label(self) -> None:
        self.assertEqual(["i", "ii", "1", "2", ""], self.labels_in_pdf())

    def test_the_label_tree_read_back_is_the_planned_one(self) -> None:
        self.assertEqual((ROMAN_THEN_DECIMAL_THEN_NONE, EXIT_OK), (self.ranges_in_pdf(), self.run.code))
        self.assertEqual(ROMAN_THEN_DECIMAL_THEN_NONE, self.run.payload()["read_back"])

    def test_the_engine_cache_still_holds_the_rewritten_pdf(self) -> None:
        self.assertTrue(MarkerCache(self.pdf, MODE_TEXT_LAYER).holds(ALL_PAGES))

    def test_no_temporary_file_remains_beside_the_pdf(self) -> None:
        self.assertEqual([f"{BASENAME}.pdf"], sorted(path.name for path in self.vault.library.iterdir()))


class TestAStaleEngineCacheStaysStale(LabelVaultCase):
    def setUp(self) -> None:
        super().setUp()
        MarkerCache(self.pdf, MODE_TEXT_LAYER).save(ALL_PAGES, CACHED_PAYLOAD)
        TextPdf(self.pdf, PAGES + 1).write()
        CapturedRun(["labels", f"{BASENAME}.pdf", "--apply"]).go()

    def test_an_entry_stale_before_the_write_is_not_revalidated_by_it(self) -> None:
        self.assertFalse(MarkerCache(self.pdf, MODE_TEXT_LAYER).holds(ALL_PAGES))


class TestAnUncitableWorkIsNeverLabelled(LabelVaultCase):
    NOTE_TEXT = f"{UNCITABLE_FRONTMATTER}\n{LINK_LINE}\n\n{BODY}"

    def test_both_forms_exit_one_naming_the_field(self) -> None:
        for flags in ((), ("--apply",)):
            run = CapturedRun(["labels", f"{BASENAME}.pdf", *flags]).go()
            self.assertEqual((EXIT_USAGE, True), (run.code, "uncitable" in run.errors), flags)

    def test_the_pdf_is_untouched(self) -> None:
        CapturedRun(["labels", f"{BASENAME}.pdf", "--apply"]).go()
        self.assertEqual([""] * PAGES, self.labels_in_pdf())


class TestAWorkWithoutABodyIsNeverLabelled(LabelVaultCase):
    NOTE_TEXT = f"{FRONTMATTER}\n{LINK_LINE}\n"

    def test_the_refusal_names_accept(self) -> None:
        run = CapturedRun(["labels", f"{BASENAME}.pdf", "--apply"]).go()
        self.assertEqual((EXIT_USAGE, True), (run.code, "accept" in run.errors))


class TestLabelRanges(unittest.TestCase):
    def _ranges(self, folios: dict[int, str | None], page_count: int) -> list[tuple]:
        return [(found.start_page, found.parts.prefix, found.parts.style, found.parts.number)
                for found in LabelRanges(folios, page_count).all()]

    def test_a_prefixed_folio_run_is_one_range_carrying_its_prefix(self) -> None:
        self.assertEqual([(1, "A-", "D", 3)], self._ranges({1: "A-3", 2: "A-4"}, 2))

    def test_an_uppercase_roman_run_keeps_its_case(self) -> None:
        self.assertEqual([(1, "", "R", 4)], self._ranges({1: "IV", 2: "V"}, 2))

    def test_a_folio_with_no_number_is_a_range_of_its_own(self) -> None:
        self.assertEqual([(1, "Plate", "", 0), (2, "", "D", 7)], self._ranges({1: "Plate", 2: "7"}, 2))

    def test_a_break_in_the_numbering_opens_a_new_range(self) -> None:
        self.assertEqual([(1, "", "D", 7), (2, "", "D", 9)], self._ranges({1: "7", 2: "9"}, 2))

    def test_pages_without_a_folio_share_one_empty_range(self) -> None:
        self.assertEqual([(1, "", "", 0), (3, "", "D", 1)], self._ranges({3: "1"}, 3))

    def test_roman_numerals_read_subtractively(self) -> None:
        self.assertEqual((4, 9, 14, 40, 90, 1994),
                         tuple(roman_value(n) for n in ("iv", "ix", "xiv", "xl", "xc", "mcmxciv")))


if __name__ == "__main__":
    unittest.main()
