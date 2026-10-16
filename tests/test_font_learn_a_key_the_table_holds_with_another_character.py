from __future__ import annotations

import json
import unittest

from _support import LiveTree

LiveTree.activate()

from _font_fixtures import LASY9, ScratchDirectory, SilentCommand

from _clean.fontcommands import FontCommands

GLYPH = "a51"
KEY = f"{LASY9}|{GLYPH}"
HELD = {"unicode": "◊", "method": "user"}


class LearnOverAHeldKeyTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch = ScratchDirectory(self)
        self.table_path = self.scratch.path / "identities.json"
        self.table_path.write_text(json.dumps({KEY: HELD}, ensure_ascii=False), encoding="utf-8")
        self.learn = SilentCommand(FontCommands(identities_path=self.table_path).learn)

    def learned(self, unicode: str) -> dict:
        return json.loads(self.learn.run(font=LASY9, glyph=GLYPH, unicode=unicode, method="user",
                                         equals_sign=False, apply=True))

    def table(self) -> dict:
        return json.loads(self.table_path.read_text(encoding="utf-8"))


class TestADifferingCharacterIsAConflict(LearnOverAHeldKeyTestCase):
    def test_the_table_keeps_its_entry(self) -> None:
        self.learned("□")
        self.assertEqual(HELD, self.table()[KEY])

    def test_the_report_names_the_conflict_and_writes_nothing(self) -> None:
        report = self.learned("□")
        self.assertEqual(("conflict", HELD, False), (report["status"], report["conflict"], report["written"]))


class TestTheSameCharacterIsNoConflict(LearnOverAHeldKeyTestCase):
    def test_the_entry_is_written(self) -> None:
        self.assertEqual(True, self.learned("◊")["written"])


if __name__ == "__main__":
    unittest.main()
