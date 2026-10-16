from __future__ import annotations

import contextlib
import io
import json
import unittest

from _support import LiveTree

LiveTree.activate()

from _extract.cli import main
from _vaults import LinedPdf, TempVault

EXTRACT_DIRS = ("LIBRARY_DIR", "CORPUS_DIR")
BASENAME = "Doe - 2020 - A Work"
NOTE_TEXT = "---\ntitle: A Work\ntype: book\n---\n\n[Doe - 2020 - A Work.pdf](zotero://open-pdf/x)\n"
LETTERS = "abcdefghijklmnopqrstuvwxyz"
LICENCE_FOOTER = ["Downloaded from a collections service on 12 March 2019", "© A University Press, 2007"]
CLOSING_LINE = "© A University Press closes the argument of this page."
PAGE_COUNT = 30
PROSE_LINES = 7
OUTLINE = [[1, "Introduction", 2], [1, "Chapter One", 10], [1, "Chapter Two", 20]]


def prose(file_page: int) -> list[str]:
    word = LETTERS[file_page % len(LETTERS)] * 3 + LETTERS[file_page // len(LETTERS)]
    return [f"The argument turns to {word} on this page, line {line}." for line in range(PROSE_LINES)]


def pages_footed(footed) -> list[list[str]]:
    return [prose(page) + LICENCE_FOOTER if footed(page) else prose(page) for page in range(1, PAGE_COUNT + 1)]


class ScopeListingCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault(*EXTRACT_DIRS).activate()
        self.addCleanup(self.vault.discard)
        (self.vault.corpus / f"{BASENAME}.md").write_text(NOTE_TEXT, encoding="utf-8")

    def listed_lines(self, pages: list[list[str]]) -> dict[int, list[str]]:
        LinedPdf(self.vault.library / f"{BASENAME}.pdf", pages, OUTLINE).write()
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            main(["scope", f"{BASENAME}.pdf"])
        return {page["file_page"]: page["lines"] for page in json.loads(output.getvalue())["pages"]}


class TestAFooterRecurringOnMostPages(ScopeListingCase):
    def test_a_two_line_licence_footer_on_every_page_is_left_out_of_the_lines(self) -> None:
        listed = self.listed_lines(pages_footed(lambda page: True))
        self.assertEqual({page: prose(page) for page in listed}, listed)

    def test_a_line_printed_at_the_foot_of_one_page_only_is_kept(self) -> None:
        pages = pages_footed(lambda page: True)
        pages[1] = prose(2) + [CLOSING_LINE]
        self.assertEqual(prose(2) + [CLOSING_LINE], self.listed_lines(pages)[2])


class TestAFooterRecurringOnFewPages(ScopeListingCase):
    def test_a_footer_printed_on_under_half_the_pages_stays_in_the_lines(self) -> None:
        listed = self.listed_lines(pages_footed(lambda page: page % 3 == 0))
        self.assertEqual(prose(PAGE_COUNT) + LICENCE_FOOTER, listed[PAGE_COUNT])


if __name__ == "__main__":
    unittest.main()
