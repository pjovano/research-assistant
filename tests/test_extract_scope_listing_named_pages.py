from __future__ import annotations

import contextlib
import io
import json
import unittest

from _support import LiveTree

LiveTree.activate()

from _extract.cli import main
from _extract.console import EXIT_USAGE
from _vaults import LinedPdf, TempVault

EXTRACT_DIRS = ("LIBRARY_DIR", "CORPUS_DIR")
BASENAME = "Doe - 2020 - A Work"
NOTE_TEXT = "---\ntitle: A Work\ntype: book\n---\n\n[Doe - 2020 - A Work.pdf](zotero://open-pdf/x)\n"
PROSE = ["The argument of the work runs on across this page,", "and the next line carries it further still."]
PAGE_COUNT = 30
OUTLINE = [[1, "Contents", 2], [1, "Introduction", 4], [1, "Chapter One", 10], [1, "Chapter Two", 20]]
UNLISTED_PAGE = 15


class TestPagesNamedToTheScopeListing(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault(*EXTRACT_DIRS).activate()
        self.addCleanup(self.vault.discard)
        (self.vault.corpus / f"{BASENAME}.md").write_text(NOTE_TEXT, encoding="utf-8")
        LinedPdf(self.vault.library / f"{BASENAME}.pdf", [PROSE] * PAGE_COUNT, OUTLINE).write()

    def scope(self, *options: str) -> tuple[int, str]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            exit_code = main(["scope", f"{BASENAME}.pdf", *options])
        return exit_code, output.getvalue()

    def listed(self, *options: str) -> dict[int, dict]:
        return {page["file_page"]: page for page in json.loads(self.scope(*options)[1])["pages"]}

    def test_a_page_the_listing_does_not_name_is_unlisted_by_default(self) -> None:
        self.assertNotIn(UNLISTED_PAGE, self.listed())

    def test_a_named_page_is_listed_with_its_text_layer_lines(self) -> None:
        page = self.listed("--page", str(UNLISTED_PAGE))[UNLISTED_PAGE]
        self.assertEqual(PROSE, page["lines"])

    def test_a_named_page_carries_the_fields_of_a_listed_page(self) -> None:
        pages = self.listed("--page", str(UNLISTED_PAGE))
        self.assertEqual(set(pages[1]), set(pages[UNLISTED_PAGE]))

    def test_a_named_page_keeps_every_page_listed_before(self) -> None:
        self.assertLessEqual(set(self.listed()), set(self.listed("--page", str(UNLISTED_PAGE))))

    def test_a_named_page_outside_the_pdf_is_refused(self) -> None:
        self.assertEqual(EXIT_USAGE, self.scope("--page", str(PAGE_COUNT + 1))[0])


if __name__ == "__main__":
    unittest.main()
