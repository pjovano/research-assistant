from __future__ import annotations

import unittest
from unittest import mock

from _support import LiveTree

LiveTree.activate()

from _clean.cleaning import InPlaceClean
from _font_fixtures import VaultTestCase
from _vaults import TextPdf


class TestACleanWhoseRewriteCannotBeFlushedToDisk(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.pdf_path = TextPdf(self.vault.inbox / "work.pdf").write()
        self.before = self.pdf_path.read_bytes()
        with mock.patch("os.fsync", side_effect=OSError("disk full")), self.assertRaises(OSError):
            InPlaceClean(self.pdf_path).run()

    def test_the_inbox_file_stays_byte_identical(self) -> None:
        self.assertEqual(self.before, self.pdf_path.read_bytes())

    def test_no_temporary_file_is_left_behind(self) -> None:
        self.assertFalse(self.temporary_of(self.pdf_path).exists())


if __name__ == "__main__":
    unittest.main()
