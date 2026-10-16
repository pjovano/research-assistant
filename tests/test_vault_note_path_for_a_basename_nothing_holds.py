from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

import vault
from _vaults import TempVault

BASENAME = "Author - 2000 - A Work"


class TestTheNotePathForABasename(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("CORPUS_DIR").activate()
        self.addCleanup(self.vault.discard)

    def test_a_held_corpus_file_is_the_note_path(self) -> None:
        vault.corpus_path(BASENAME).write_text("---\n---\n", encoding="utf-8")
        self.assertEqual(vault.corpus_path(BASENAME), vault.note_path_for(BASENAME))

    def test_a_held_transcript_is_the_note_path(self) -> None:
        vault.transcript_path(BASENAME).write_text("---\n---\n", encoding="utf-8")
        self.assertEqual(vault.transcript_path(BASENAME), vault.note_path_for(BASENAME))

    def test_a_basename_nothing_holds_names_the_transcript_path_which_does_not_exist(self) -> None:
        path = vault.note_path_for(BASENAME)
        self.assertEqual((vault.transcript_path(BASENAME), False), (path, path.exists()))

    def test_the_held_note_path_name_is_the_note_path_for(self) -> None:
        self.assertIs(vault.note_path_for, vault.held_note_path)


if __name__ == "__main__":
    unittest.main()
