from __future__ import annotations

import unittest
from unittest import mock

from _support import LiveTree

LiveTree.activate()

from _file.filing import AttachmentWatcher, FilingCompletion, Placement
from _file.notes import CorpusNote
from _file.refile import REFILING_DIR_NAME, RefileTarget, Refiler
from _file_fixtures import (
    ATTACHMENT_LINK,
    CITEKEY,
    OTHER_WORK_PDF_NAME,
    PLACED_PDF_NAME,
    Citation,
    VaultTestCase,
    saved_with_key,
)
from _vaults import TextPdf

STATUS_REFILED_UNVERIFIED = "refiled-unverified"
STATUS_REFILE_RENAMED = "refile-renamed"


class RefileTestCase(VaultTestCase):
    def refiled(self, placement: Placement) -> dict:
        self.library_pdf = TextPdf(self.vault.library / PLACED_PDF_NAME, pages=1).write()
        CorpusNote(PLACED_PDF_NAME).write(Citation().fields(), ATTACHMENT_LINK, "")
        self.stub_zotero(save_item_with_attachment=lambda item, pdf: saved_with_key(),
                         get_citation_key=lambda item_key: CITEKEY)
        with mock.patch.object(AttachmentWatcher, "await_placement", return_value=placement):
            return Refiler(RefileTarget(PLACED_PDF_NAME), FilingCompletion()).execute()


class TestARefileZotmoovNeverPlaces(RefileTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.report = self.refiled(Placement())

    def test_the_status_is_refiled_unverified(self) -> None:
        self.assertEqual(STATUS_REFILED_UNVERIFIED, self.report["status"])

    def test_the_library_pdf_is_put_back(self) -> None:
        self.assertTrue(self.library_pdf.exists())


class TestARefileZotmoovPlacesUnderAnotherName(RefileTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.report = self.refiled(Placement(None, OTHER_WORK_PDF_NAME))

    def test_the_status_is_refile_renamed_naming_the_other_name(self) -> None:
        renamed = (self.report["status"], self.report["placed_as"])
        self.assertEqual((STATUS_REFILE_RENAMED, OTHER_WORK_PDF_NAME), renamed)

    def test_the_library_pdf_is_not_put_back(self) -> None:
        self.assertFalse(self.library_pdf.exists())

    def test_the_holding_copy_is_kept(self) -> None:
        self.assertTrue((self.vault.library / REFILING_DIR_NAME / PLACED_PDF_NAME).exists())


if __name__ == "__main__":
    unittest.main()
