from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import vault

ORIGINAL_TEXT = "---\ntitle: Original\n---\n\nBody.\n"
REPLACED_TEXT = "---\ntitle: Replaced\n---\n\nBody.\n"
FOREIGN_TEXT = "---\ntitle: Edited elsewhere\n---\n\nBody.\n"
TEMPORARY_SUFFIX = ".tmp.pdf"


class NoteDirectory:
    def __init__(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.note = Path(self._directory.name) / "note.md"

    def leftovers(self) -> list[str]:
        return sorted(path.name for path in self.note.parent.iterdir() if path != self.note)

    def discard(self) -> None:
        self._directory.cleanup()


class ReplacementTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = NoteDirectory()
        self.addCleanup(self.directory.discard)
        self.directory.note.write_text(ORIGINAL_TEXT, encoding="utf-8")


class TestGuardedNote(ReplacementTestCase):
    def test_a_replace_after_a_read_writes_the_new_text(self) -> None:
        note = vault.GuardedNote(self.directory.note)
        note.text()
        note.replace(REPLACED_TEXT)
        self.assertEqual(REPLACED_TEXT, self.directory.note.read_text(encoding="utf-8"))

    def test_a_replace_leaves_no_partial_file_beside_the_note(self) -> None:
        vault.GuardedNote(self.directory.note).replace(REPLACED_TEXT)
        self.assertEqual([], self.directory.leftovers())

    def test_a_note_changed_after_the_read_is_refused(self) -> None:
        note = vault.GuardedNote(self.directory.note)
        note.text()
        self.directory.note.write_text(FOREIGN_TEXT, encoding="utf-8")
        with self.assertRaises(vault.NoteChangedOnDisk):
            note.replace(REPLACED_TEXT)

    def test_a_refused_replace_keeps_the_foreign_edit(self) -> None:
        note = vault.GuardedNote(self.directory.note)
        note.text()
        self.directory.note.write_text(FOREIGN_TEXT, encoding="utf-8")
        with self.assertRaises(vault.NoteChangedOnDisk):
            note.replace(REPLACED_TEXT)
        self.assertEqual(FOREIGN_TEXT, self.directory.note.read_text(encoding="utf-8"))

    def test_a_note_deleted_after_the_read_is_refused(self) -> None:
        note = vault.GuardedNote(self.directory.note)
        note.text()
        self.directory.note.unlink()
        with self.assertRaises(vault.NoteChangedOnDisk):
            note.replace(REPLACED_TEXT)

    def test_a_remove_deletes_the_note(self) -> None:
        vault.GuardedNote(self.directory.note).remove()
        self.assertFalse(self.directory.note.exists())

    def test_a_remove_of_a_note_changed_after_the_read_is_refused(self) -> None:
        note = vault.GuardedNote(self.directory.note)
        note.text()
        self.directory.note.write_text(FOREIGN_TEXT, encoding="utf-8")
        with self.assertRaises(vault.NoteChangedOnDisk):
            note.remove()
        self.assertEqual(FOREIGN_TEXT, self.directory.note.read_text(encoding="utf-8"))

    def test_the_text_is_the_snapshot_of_the_first_read(self) -> None:
        note = vault.GuardedNote(self.directory.note)
        note.text()
        self.directory.note.write_text(FOREIGN_TEXT, encoding="utf-8")
        self.assertEqual(ORIGINAL_TEXT, note.text())

    def test_a_second_replace_follows_the_first(self) -> None:
        note = vault.GuardedNote(self.directory.note)
        note.text()
        note.replace(REPLACED_TEXT)
        note.replace(ORIGINAL_TEXT)
        self.assertEqual(ORIGINAL_TEXT, self.directory.note.read_text(encoding="utf-8"))


class TestStoredNoteGuard(ReplacementTestCase):
    def test_a_stored_note_refuses_a_write_over_a_foreign_edit(self) -> None:
        stored = vault.StoredNote(self.directory.note)
        meta, body = stored.read()
        self.directory.note.write_text(FOREIGN_TEXT, encoding="utf-8")
        with self.assertRaises(vault.NoteChangedOnDisk):
            stored.write(meta, body)

    def test_a_stored_note_refuses_a_write_over_a_foreign_edit_made_after_its_frontmatter_was_read(self) -> None:
        stored = vault.StoredNote(self.directory.note)
        meta = stored.frontmatter()
        self.directory.note.write_text(FOREIGN_TEXT, encoding="utf-8")
        with self.assertRaises(vault.NoteChangedOnDisk):
            stored.write(meta, "Body.")


class TestReplacementFile(ReplacementTestCase):
    def test_an_uncommitted_replacement_leaves_the_target_and_no_partial(self) -> None:
        with vault.ReplacementFile(self.directory.note, TEMPORARY_SUFFIX) as replacement:
            replacement.path.write_text(REPLACED_TEXT, encoding="utf-8")
        self.assertEqual((ORIGINAL_TEXT, []),
                         (self.directory.note.read_text(encoding="utf-8"), self.directory.leftovers()))

    def test_a_committed_replacement_takes_the_place_of_the_target(self) -> None:
        with vault.ReplacementFile(self.directory.note, TEMPORARY_SUFFIX) as replacement:
            replacement.path.write_text(REPLACED_TEXT, encoding="utf-8")
            replacement.commit()
        self.assertEqual((REPLACED_TEXT, []),
                         (self.directory.note.read_text(encoding="utf-8"), self.directory.leftovers()))


if __name__ == "__main__":
    unittest.main()
