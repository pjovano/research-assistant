from __future__ import annotations

import unittest
from unittest import mock

from _support import LiveTree

LiveTree.activate()

import pymupdf

import vault

from _volumes.document import VolumeDocument
from _volumes.extraction import ChapterExtraction, ChosenChapter, PageRange
from _vaults import TempVault, TextPdf

OUTLINE = [[1, "Chapter One", 1], [1, "Chapter Two", 2]]
HALF_WRITTEN = b"%PDF-1.7\n"


def save_interrupted_halfway(_document: pymupdf.Document, path, *_args, **_kwargs) -> None:
    with open(path, "wb") as written:
        written.write(HALF_WRITTEN)
    raise RuntimeError("the process was stopped while saving")


class TestAChapterWhoseSaveIsInterrupted(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("INBOX_DIR", "LIBRARY_DIR", "VOLUMES_DIR", "CORPUS_DIR").activate()
        self.addCleanup(self.vault.discard)
        source = VolumeDocument.read(TextPdf(self.vault.volumes / "collected.pdf", pages=2, outline=OUTLINE).write())
        extraction = ChapterExtraction(source, ChosenChapter(PageRange(1, 1), "Chapter One"))
        with mock.patch.object(pymupdf.Document, "save", save_interrupted_halfway), \
                self.assertRaises(RuntimeError):
            extraction.write()

    def test_no_pdf_is_left_in_the_inbox_for_the_next_batch(self) -> None:
        self.assertEqual([], vault.list_pdfs(vault.INBOX_DIR))

    def test_no_temporary_file_is_left_in_the_inbox(self) -> None:
        self.assertEqual([], list(vault.INBOX_DIR.iterdir()))


if __name__ == "__main__":
    unittest.main()
