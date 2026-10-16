from __future__ import annotations

import json
import unittest
from unittest import mock

from _support import LiveTree

LiveTree.activate()

from _font_fixtures import ScratchDirectory

from _clean.glyphs import Identity, IdentityTable

FAMILY = "LASY9"
FIRST_GLYPH = "a51"
SECOND_GLYPH = "a52"


class IdentityTableTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch = ScratchDirectory(self)
        self.path = self.scratch.path / "identities.json"

    def loaded_table(self) -> IdentityTable:
        table = IdentityTable(self.path)
        table.entries()
        return table

    def learn(self, table: IdentityTable, glyph: str, character: str) -> None:
        table.write(*table.entry_for(FAMILY, glyph, Identity(character, "worker")))

    def on_disk(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8"))


class TestTwoWritersLoadedBeforeEitherWrites(IdentityTableTestCase):
    def test_both_entries_are_kept(self) -> None:
        first, second = self.loaded_table(), self.loaded_table()
        self.learn(first, FIRST_GLYPH, "◊")
        self.learn(second, SECOND_GLYPH, "□")
        self.assertEqual({f"{FAMILY}|{FIRST_GLYPH}", f"{FAMILY}|{SECOND_GLYPH}"}, set(self.on_disk()))


class TestAWriteThatFailsBeforeReachingDisk(IdentityTableTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.learn(IdentityTable(self.path), FIRST_GLYPH, "◊")
        with mock.patch("os.fsync", side_effect=OSError("disk full")), self.assertRaises(OSError):
            self.learn(IdentityTable(self.path), SECOND_GLYPH, "□")

    def test_the_table_keeps_its_earlier_entries_whole(self) -> None:
        self.assertEqual({f"{FAMILY}|{FIRST_GLYPH}"}, set(self.on_disk()))

    def test_no_temporary_file_remains(self) -> None:
        self.assertEqual(["identities.json"], sorted(path.name for path in self.scratch.path.iterdir()))


if __name__ == "__main__":
    unittest.main()
