from __future__ import annotations

import json
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import pymupdf
from _font_fixtures import MisreadFont, MisreadFontPdf, NoPixelChecks, ScratchDirectory, SilentCommand

from _clean.fontcommands import FontCommands
from _vaults import TempVault

MISREAD_WORK = "Doe - 2020 - A Work.pdf"
DINGBAT_OF_A60 = "❁"
DINGBAT_OF_A61 = "❂"
MISREAD_FONT = MisreadFont("GHIJKL+LASY9", ("a61", "a60"), (DINGBAT_OF_A61, DINGBAT_OF_A60))
PROSE_PAGES = 2
PROSE = "The argument of the work runs on across this page."
PROSE_ORIGIN = (72, 72)


class FlaggedPagesCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("INBOX_DIR", "LIBRARY_DIR", "VOLUMES_DIR").activate()
        self.addCleanup(self.vault.discard)
        self.scratch = ScratchDirectory(self)

    def listed(self, pdf: Path) -> dict:
        commands = FontCommands(self.scratch.table({}).path, NoPixelChecks())
        return json.loads(SilentCommand(commands.pages).run(pdf=str(pdf), table=None))

    def misread_then_prose(self) -> Path:
        misread = MisreadFontPdf((MISREAD_FONT,)).write(self.vault.library / "misread.pdf")
        with pymupdf.open(misread) as document:
            for _ in range(PROSE_PAGES):
                document.new_page().insert_text(PROSE_ORIGIN, PROSE)
            document.save(self.vault.library / MISREAD_WORK)
        return self.vault.library / MISREAD_WORK


class TestThePagesFlaggedCodesOccurOn(FlaggedPagesCase):
    def test_only_the_page_setting_the_misread_font_is_listed(self) -> None:
        self.assertEqual([1], self.listed(self.misread_then_prose())["pages"])

    def test_the_listing_counts_every_page_of_the_pdf(self) -> None:
        self.assertEqual(1 + PROSE_PAGES, self.listed(self.misread_then_prose())["page_count"])

    def test_a_pdf_without_a_flagged_code_lists_no_page(self) -> None:
        prose = self.vault.library / MISREAD_WORK
        with pymupdf.open() as document:
            document.new_page().insert_text(PROSE_ORIGIN, PROSE)
            document.save(prose)
        self.assertEqual([], self.listed(prose)["pages"])


if __name__ == "__main__":
    unittest.main()
