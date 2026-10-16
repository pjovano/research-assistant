from __future__ import annotations

import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _port_fakes import FakeTrash
from _ports.host import Trash
from _rag_fakes import temp_directory


class TrashContract:
    def trash(self) -> Trash:
        raise NotImplementedError

    def setUp(self) -> None:
        self.directory = temp_directory(self) / "drafts"
        self.directory.mkdir()

    def written(self, name: str) -> Path:
        path = self.directory / name
        path.write_text("draft\n", encoding="utf-8")
        return path

    def test_a_discarded_file_leaves_its_place(self) -> None:
        discarded = self.written("draft.docx")
        self.trash().discard(discarded)
        self.assertFalse(discarded.exists())

    def test_the_other_files_of_the_directory_stay(self) -> None:
        kept = self.written("kept.docx")
        self.trash().discard(self.written("draft.docx"))
        self.assertTrue(kept.exists())


class TestFakeTrashKeepsTheContract(TrashContract, unittest.TestCase):
    def trash(self) -> Trash:
        return FakeTrash(self.directory.parent / "bin")


if __name__ == "__main__":
    unittest.main()
