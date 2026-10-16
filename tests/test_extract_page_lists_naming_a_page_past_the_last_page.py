from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

import pagetext
import vault

from _extract.checks import STATUS_DOUBTFUL, PageVerdict
from _extract.report import DoubtfulReport
from _vaults import TempVault, TextPdf

PAGES = 3
PAST_THE_END = PAGES + 7
WITHIN = 2


def doubtful(file_page: int) -> PageVerdict:
    return PageVerdict(file_page, STATUS_DOUBTFUL, "length", "")


class TestAPageListNamingAPagePastTheLastPage(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("LIBRARY_DIR", "CORPUS_DIR").activate()
        self.addCleanup(self.vault.discard)
        self.pdf = TextPdf(vault.LIBRARY_DIR / "Doe - 2020 - A Work.pdf", PAGES).write()
        listed = DoubtfulReport(self.pdf).as_list([doubtful(PAST_THE_END), doubtful(WITHIN)])
        self.renders = {entry["file_page"]: entry["render"] for entry in listed}

    def test_a_page_within_the_pdf_is_paired_with_its_own_render(self) -> None:
        [own_render] = pagetext.render_pages(self.pdf, [WITHIN])
        self.assertEqual(str(own_render), self.renders[WITHIN])

    def test_a_page_past_the_last_page_has_no_render(self) -> None:
        self.assertIsNone(self.renders[PAST_THE_END])


if __name__ == "__main__":
    unittest.main()
