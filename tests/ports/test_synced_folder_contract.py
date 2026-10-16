from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from _support import LiveTree

LiveTree.activate()

from _adapters.host.icloud import SF_DATALESS, ICloudFolder
from _port_fakes import FakeSyncedFolder
from _ports.host import SyncedFolder
from _rag_fakes import temp_directory

ORIGINAL = "note.md"
PDF = "Hegel - 1812 - Logic.pdf"
NUMBERED_PDF = "Hegel - 1812 - Logic 2.pdf"
CONFLICTED_NOTE = "note (conflicted copy 2026-09-03).md"
UNRELATED_FLAGS = 0x20


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

    def test_a_directory_that_does_not_exist_has_no_conflict_copy(self) -> None:
        self.assertEqual([], self.synced_folder().conflict_copies(self.directory / "absent"))

    def test_a_file_whose_bytes_are_on_disk_is_downloaded(self) -> None:
        self.assertFalse(self.synced_folder().not_downloaded(self.written(ORIGINAL)))


class TestFakeSyncedFolderKeepsTheContract(SyncedFolderContract, unittest.TestCase):
    def synced_folder(self) -> SyncedFolder:
        return FakeSyncedFolder()

    def conflict_copy_name(self, original: str) -> str:
        stem, suffix = original.rsplit(".", 1)
        return f"{stem} 2.{suffix}"


class TestICloudFolderKeepsTheContract(SyncedFolderContract, unittest.TestCase):
    def synced_folder(self) -> SyncedFolder:
        return ICloudFolder()

    def conflict_copy_name(self, original: str) -> str:
        stem, suffix = original.rsplit(".", 1)
        return f"{stem} 2.{suffix}"


class TestICloudConflictCopiesKeepTodaysVerdicts(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = temp_directory(self)
        self.notes = self.directory / "corpus"
        self.notes.mkdir()

    def written(self, name: str, text: str = "text\n", directory: Path | None = None) -> Path:
        path = (directory or self.directory) / name
        path.write_text(text, encoding="utf-8")
        return path

    def copies(self) -> list[str]:
        return [path.name for path in ICloudFolder(self.notes).conflict_copies(self.directory)]

    def test_a_numbered_file_without_its_original_is_no_copy(self) -> None:
        self.written("note 2.md")
        self.assertEqual([], self.copies())

    def test_a_numbered_note_naming_another_citekey_is_no_copy(self) -> None:
        self.written(ORIGINAL, "---\ncitekey: hegel1812\n---\n")
        self.written("note 2.md", "---\ncitekey: hegel1816\n---\n")
        self.assertEqual([], self.copies())

    def test_a_numbered_pdf_with_a_note_of_its_own_is_no_copy(self) -> None:
        self.written(PDF)
        self.written(NUMBERED_PDF)
        self.written("Hegel - 1812 - Logic 2.md", directory=self.notes)
        self.assertEqual([], self.copies())

    def test_a_numbered_pdf_without_a_note_of_its_own_is_a_copy(self) -> None:
        self.written(PDF)
        self.written(NUMBERED_PDF)
        self.assertEqual([NUMBERED_PDF], self.copies())

    def test_a_conflicted_copy_is_a_copy_without_its_original(self) -> None:
        self.written(CONFLICTED_NOTE)
        self.assertEqual([CONFLICTED_NOTE], self.copies())


class StatWithFlags:
    def __init__(self, flags: int) -> None:
        self._flags = flags

    def __call__(self, path: Path) -> SimpleNamespace:
        return SimpleNamespace(st_flags=self._flags)


class TestICloudPlaceholders(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = temp_directory(self)
        self.pdf = self.directory / PDF

    def test_a_dataless_file_is_not_downloaded(self) -> None:
        self.pdf.write_bytes(b"")
        self.assertTrue(ICloudFolder(lstat=StatWithFlags(SF_DATALESS)).not_downloaded(self.pdf))

    def test_a_file_whose_flags_omit_dataless_is_downloaded(self) -> None:
        self.pdf.write_bytes(b"%PDF")
        self.assertFalse(ICloudFolder(lstat=StatWithFlags(UNRELATED_FLAGS)).not_downloaded(self.pdf))

    def test_a_stat_without_flags_reads_as_downloaded(self) -> None:
        self.pdf.write_bytes(b"%PDF")
        self.assertFalse(ICloudFolder(lstat=lambda path: SimpleNamespace()).not_downloaded(self.pdf))

    def test_a_file_with_an_icloud_stub_beside_it_is_not_downloaded(self) -> None:
        (self.directory / f".{PDF}.icloud").write_bytes(b"")
        self.assertTrue(ICloudFolder().not_downloaded(self.pdf))

    def test_the_icloud_stub_itself_stands_for_a_file_not_downloaded(self) -> None:
        stub = self.directory / f".{PDF}.icloud"
        stub.write_bytes(b"")
        self.assertTrue(ICloudFolder().not_downloaded(stub))

    def test_a_hidden_file_that_is_no_stub_is_downloaded(self) -> None:
        hidden = self.directory / ".DS_Store"
        hidden.write_bytes(b"")
        self.assertFalse(ICloudFolder().not_downloaded(hidden))


if __name__ == "__main__":
    unittest.main()
