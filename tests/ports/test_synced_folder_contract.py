from __future__ import annotations

import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _port_fakes import FakeSyncedFolder
from _ports.host import SyncedFolder
from _rag_fakes import temp_directory

ORIGINAL = "note.md"


class SyncedFolderContract:
    def synced_folder(self) -> SyncedFolder:
        raise NotImplementedError

    def conflict_copy_name(self, original: str) -> str:
        raise NotImplementedError

    def setUp(self) -> None:
        self.directory = temp_directory(self)

    def written(self, name: str) -> Path:
        path = self.directory / name
        path.write_text("text\n", encoding="utf-8")
        return path

    def test_a_directory_without_conflicts_has_no_conflict_copy(self) -> None:
        self.written(ORIGINAL)
        self.assertEqual([], self.synced_folder().conflict_copies(self.directory))

    def test_the_conflict_copy_is_listed_and_its_original_is_not(self) -> None:
        self.written(ORIGINAL)
        copy = self.written(self.conflict_copy_name(ORIGINAL))
        self.assertEqual([copy], self.synced_folder().conflict_copies(self.directory))

    def test_a_file_whose_bytes_are_on_disk_is_downloaded(self) -> None:
        self.assertFalse(self.synced_folder().not_downloaded(self.written(ORIGINAL)))


class TestFakeSyncedFolderKeepsTheContract(SyncedFolderContract, unittest.TestCase):
    def synced_folder(self) -> SyncedFolder:
        return FakeSyncedFolder()

    def conflict_copy_name(self, original: str) -> str:
        stem, suffix = original.rsplit(".", 1)
        return f"{stem} 2.{suffix}"


if __name__ == "__main__":
    unittest.main()
