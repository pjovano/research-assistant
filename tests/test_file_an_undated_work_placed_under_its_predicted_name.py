from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

import vault
from _file.filing import AttachmentWatcher
from _file.preview import UNDATED_YEAR
from _file_fixtures import ATTACHMENT_LINK, CITEKEY, PDF_BYTES, PREDICTED_PDF_NAME, VaultTestCase

ANOTHER_UNDATED_NAME = "Roe - n.d. - Another Work.pdf"


class TestAnUndatedWorkPlacedUnderItsPredictedName(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.placed = self.vault.library / PREDICTED_PDF_NAME
        self.placed.write_bytes(PDF_BYTES)

    def test_the_placed_pdf_is_in_the_library(self) -> None:
        self.assertTrue(AttachmentWatcher(PREDICTED_PDF_NAME).in_library(self.placed))

    def test_the_placement_is_verified(self) -> None:
        self.stub_zotero(get_attachments=lambda citekey: [{"path": str(self.placed), "open": ATTACHMENT_LINK}])
        placement = AttachmentWatcher(PREDICTED_PDF_NAME, timeout=0).await_placement(CITEKEY)
        self.assertEqual(PREDICTED_PDF_NAME, placement.verified.pdf_name)

    def test_another_undated_name_is_not_taken_for_it(self) -> None:
        other = self.vault.library / ANOTHER_UNDATED_NAME
        other.write_bytes(PDF_BYTES)
        self.assertFalse(AttachmentWatcher(PREDICTED_PDF_NAME).in_library(other))


class TestTheUndatedMarker(unittest.TestCase):
    def test_it_is_the_one_the_citekey_rules_use(self) -> None:
        self.assertEqual(vault.citekey_year({}), UNDATED_YEAR)


if __name__ == "__main__":
    unittest.main()
