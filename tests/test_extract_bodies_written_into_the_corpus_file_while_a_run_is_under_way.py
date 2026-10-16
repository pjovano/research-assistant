from __future__ import annotations

import unittest
from unittest import mock

from _support import LiveTree

LiveTree.activate()

import vault

from _extract.acceptance import Acceptance
from _extract.paths import CorpusFile, PdfLocator
from _extract.request import ExtractionRequest
from _extract.stage import BodyTarget
from _extract.trial import TrialNote
from _vaults import TempVault, TextPdf

BASENAME = "Doe - 2020 - A Work"
FRONTMATTER = "---\ntitle: A Work\n---\n"
LINK_LINE = f"[{BASENAME}.pdf](zotero://open-pdf/x)"
RUN_BODY = "%% file p. 1 %%\nThe body this run built.\n"
ARRIVED_BODY = "%% file p. 1 %%\nA body another writer put in place meanwhile.\n"
TODAY = "2026-10-01"


class RacedCorpusFileTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("LIBRARY_DIR", "CORPUS_DIR").activate()
        self.addCleanup(self.vault.discard)
        self.pdf = TextPdf(vault.LIBRARY_DIR / f"{BASENAME}.pdf").write()
        vault.corpus_path(BASENAME).write_text(f"{FRONTMATTER}\n{LINK_LINE}\n", encoding="utf-8")
        _pdf_path, self.note = PdfLocator().with_note(str(self.pdf))

    def another_writer_puts_a_body_in_place(self) -> None:
        CorpusFile(self.pdf).write(ARRIVED_BODY, {})

    def assert_the_arrived_body_stands(self) -> None:
        self.assertEqual(ARRIVED_BODY.strip(), CorpusFile(self.pdf).body().strip())


class TestABodyWrittenWhileExtractConverts(RacedCorpusFileTestCase):
    def test_the_body_another_writer_put_in_place_is_not_overwritten(self) -> None:
        self.note.require_absent()
        self.another_writer_puts_a_body_in_place()
        target = BodyTarget.corpus_file(self.note)
        with self.assertRaises(vault.NoteChangedOnDisk):
            target.written(RUN_BODY, target.record_fields(ExtractionRequest(()), None))
        self.assert_the_arrived_body_stands()


class TestABodyWrittenBetweenAcceptsCheckAndItsWrite(RacedCorpusFileTestCase):
    def setUp(self) -> None:
        super().setUp()
        TrialNote(self.note).write(RUN_BODY, ExtractionRequest(()).record_fields())

    def test_the_body_another_writer_put_in_place_is_not_overwritten(self) -> None:
        checked = CorpusFile.require_absent

        def checked_then_raced(note: CorpusFile) -> None:
            checked(note)
            self.another_writer_puts_a_body_in_place()

        with mock.patch.object(CorpusFile, "require_absent", checked_then_raced), \
                self.assertRaises(vault.NoteChangedOnDisk):
            Acceptance(self.note, TrialNote(self.note), TODAY).accept()
        self.assert_the_arrived_body_stands()


if __name__ == "__main__":
    unittest.main()
