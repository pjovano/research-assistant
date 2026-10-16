from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

import vault
from _vault import paths
from _vaults import TempVault

WORK = "Doe - 2020 - A Work"
TALK = "Roe - 2021 - A Talk"


class TestTranscriptsNestedInTheCorpus(unittest.TestCase):
    def setUp(self) -> None:
        self._vault = TempVault("CORPUS_DIR", "TRANSCRIPTS_DIR").activate()
        vault.write_frontmatter(vault.CORPUS_DIR / f"{WORK}.md", {"title": "A work"}, "Text.")
        vault.write_frontmatter(vault.TRANSCRIPTS_DIR / f"{TALK}.md", {"title": "A talk"}, "Spoken.")

    def tearDown(self) -> None:
        self._vault.discard()

    def test_the_transcripts_directory_sits_inside_the_corpus_directory(self) -> None:
        self.assertEqual(paths.TRANSCRIPTS_DIR.parent, paths.CORPUS_DIR)

    def test_the_corpus_listing_leaves_out_a_transcript_in_the_corpus_subfolder(self) -> None:
        self.assertEqual([vault.basename_of(path) for path in vault.list_corpus_files()], [WORK])

    def test_the_held_notes_list_each_note_once(self) -> None:
        self.assertEqual(sorted(vault.basename_of(path) for path in vault.list_held_notes()), [WORK, TALK])


if __name__ == "__main__":
    unittest.main()
