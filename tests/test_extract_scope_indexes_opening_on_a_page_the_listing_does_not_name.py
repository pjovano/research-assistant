from __future__ import annotations

import contextlib
import io
import json
import unittest

from _support import LiveTree

LiveTree.activate()

from _extract.cli import main
from _extract.firstlines import FirstLines
from _vaults import LinedPdf, TempVault

EXTRACT_DIRS = ("LIBRARY_DIR", "CORPUS_DIR")
BASENAME = "Doe - 2020 - A Work"
NOTE_TEXT = "---\ntitle: A Work\ntype: book\n---\n\n[Doe - 2020 - A Work.pdf](zotero://open-pdf/x)\n"
PAGES = 60
INDEX_OPENING = 45
INDEX_LAST_PAGE = 56
PROSE = ["The argument of the work runs on across this page,", "and the next line carries it further still."]
INDEX_ENTRIES = ["Abelard, Peter 12, 45", "absolute, the 3–9", "Adorno, T. W. 88", "aesthetics 101, 140n. 3",
                 "Agamben, G. 17", "Alexander 205"]
LATER_ENTRIES = ["Kant, I. 4, 8, 15", "knowledge 33–40", "language 12", "Leibniz, G. W. 99, 102"]
OUTLINE = [[1, "Chapter One", 3], [1, "Chapter Two", 20]]
INDEX_RUN = {"first_page": INDEX_OPENING, "last_page": INDEX_LAST_PAGE, "label": "index"}


def index_book(opening_lines: list[str]) -> list[list[str]]:
    pages = [PROSE] * PAGES
    pages[INDEX_OPENING - 1] = opening_lines
    for file_page in range(INDEX_OPENING + 1, INDEX_LAST_PAGE + 1):
        pages[file_page - 1] = LATER_ENTRIES
    for file_page in range(INDEX_LAST_PAGE + 1, PAGES + 1):
        pages[file_page - 1] = []
    return pages


class IndexedPdfCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault(*EXTRACT_DIRS).activate()
        self.addCleanup(self.vault.discard)
        (self.vault.corpus / f"{BASENAME}.md").write_text(NOTE_TEXT, encoding="utf-8")

    def listing(self, pages: list[list[str]], outline: list) -> dict:
        LinedPdf(self.vault.library / f"{BASENAME}.pdf", pages, outline).write()
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            main(["scope", f"{BASENAME}.pdf"])
        return json.loads(output.getvalue())


class TestAnIndexTheTextLayerOpens(IndexedPdfCase):
    def setUp(self) -> None:
        super().setUp()
        self.scope = self.listing(index_book(["Index", *INDEX_ENTRIES]), OUTLINE)

    def test_the_page_opening_the_index_is_listed(self) -> None:
        self.assertIn(INDEX_OPENING, [page["file_page"] for page in self.scope["pages"]])

    def test_the_index_is_a_pre_labelled_run_up_to_its_last_page_of_entries(self) -> None:
        self.assertEqual([INDEX_RUN], self.scope["pre_labelled"])


class TestAnIndexTheOutlineNames(IndexedPdfCase):
    def test_an_outline_entry_naming_an_index_opens_an_index_run(self) -> None:
        outline = [*OUTLINE, [1, "Back Matter", 40], [2, "Subject Index", INDEX_OPENING]]
        scope = self.listing(index_book(LATER_ENTRIES), outline)
        self.assertEqual([INDEX_RUN], scope["pre_labelled"])


class TestAWorkWithoutAnIndex(IndexedPdfCase):
    def test_a_work_neither_the_text_layer_nor_the_outline_gives_an_index_has_no_index_run(self) -> None:
        scope = self.listing([PROSE] * PAGES, OUTLINE)
        self.assertIsNone(scope["pre_labelled"])


class TestIndexHeadings(unittest.TestCase):
    def test_an_index_heading_in_capitals_opens_an_index(self) -> None:
        self.assertTrue(FirstLines(["INDEX", *INDEX_ENTRIES]).opens_an_index())

    def test_a_name_index_opens_an_index(self) -> None:
        self.assertTrue(FirstLines(["Name Index", *INDEX_ENTRIES]).opens_an_index())

    def test_an_index_of_any_named_kind_opens_an_index(self) -> None:
        self.assertTrue(FirstLines(["Index of Passages Cited", *INDEX_ENTRIES]).opens_an_index())

    def test_a_running_head_above_the_index_heading_does_not_hide_it(self) -> None:
        self.assertTrue(FirstLines(["412", "Index", *INDEX_ENTRIES]).opens_an_index())

    def test_an_index_heading_over_entries_out_of_alphabetical_order_opens_no_index(self) -> None:
        contents = ["Index", "Preface 1", "Truth 9", "Meaning 30", "Language 52", "Belief 80", "Action 99"]
        self.assertFalse(FirstLines(contents).opens_an_index())

    def test_an_index_heading_over_prose_opens_no_index(self) -> None:
        self.assertFalse(FirstLines(["Index", *PROSE]).opens_an_index())


if __name__ == "__main__":
    unittest.main()
