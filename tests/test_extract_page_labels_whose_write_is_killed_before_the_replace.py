from __future__ import annotations

import unittest
from unittest import mock

from _support import LiveTree

LiveTree.activate()

import pymupdf

import vault

from _extract.pagelabels import PageLabelWriter
from _extract.paths import CorpusFile
from _vaults import TempVault, TextPdf

BASENAME = "Doe - 2020 - A Work"
NOTE_TEXT = (f"---\ntitle: A Work\n---\n\n[{BASENAME}.pdf](zotero://open-pdf/x)\n\n"
             "%% p. 1 (file p. 1) %%\nThe text.\n\n%% p. 2 (file p. 2) %%\nMore text.\n")


def saved_then_killed(document: pymupdf.Document, path, *args, **kwargs) -> None:
    original_save(document, path, *args, **kwargs)
    raise KeyboardInterrupt


def no_cleanup(_replacement: vault.ReplacementFile, *_exception) -> None:
    return None


original_save = pymupdf.Document.save


class TestPageLabelsWhoseWriteIsKilledBeforeTheReplace(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("LIBRARY_DIR", "CORPUS_DIR").activate()
        self.addCleanup(self.vault.discard)
        self.pdf = TextPdf(vault.LIBRARY_DIR / f"{BASENAME}.pdf", 2).write()
        vault.corpus_path(BASENAME).write_text(NOTE_TEXT, encoding="utf-8")
        writer = PageLabelWriter(self.pdf, CorpusFile(self.pdf))
        with mock.patch.object(pymupdf.Document, "save", saved_then_killed), \
                mock.patch.object(vault.ReplacementFile, "__exit__", no_cleanup), \
                self.assertRaises(KeyboardInterrupt):
            writer.apply(writer.plan())

    def test_the_left_temporary_file_is_never_listed_as_a_library_pdf(self) -> None:
        self.assertEqual([self.pdf], vault.list_pdfs(vault.LIBRARY_DIR))

    def test_the_library_pdf_is_untouched(self) -> None:
        with pymupdf.open(self.pdf) as document:
            self.assertEqual([], document.get_page_labels())


if __name__ == "__main__":
    unittest.main()
