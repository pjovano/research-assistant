from __future__ import annotations

import json
import unittest

from _support import LiveTree

LiveTree.activate()

from _font_fixtures import (
    LASY9,
    ScratchDirectory,
    SilentCommand,
)
from _clean.fontcommands import FontCommands
from _clean.glyphs import (
    METHOD_GLYPH_NAME,
    METHOD_TABLE,
    GlyphQuery,
    Identity,
    IdentityResolver,
    IdentityTable,
)


class TestIdentityTable(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch = ScratchDirectory(self)

    def test_the_glyph_name_key_outranks_the_hex_code_key(self) -> None:
        table = self.scratch.table({"LASY9|a51": {"unicode": "◊", "method": "user"},
                                    "LASY9|01": {"unicode": "x", "method": "user"}})
        self.assertEqual("◊", table.lookup(GlyphQuery("LASY9", "a51", "01")).unicode)

    def test_the_hex_code_key_serves_a_code_without_a_glyph_name(self) -> None:
        table = self.scratch.table({"LASY9|01": {"unicode": "x", "method": "user"}})
        self.assertEqual("x", table.lookup(GlyphQuery("LASY9", None, "01")).unicode)

    def test_a_table_hit_reports_the_table_method(self) -> None:
        table = self.scratch.table({"LASY9|a51": {"unicode": "◊", "method": "user"}})
        self.assertEqual(METHOD_TABLE, table.lookup(GlyphQuery("LASY9", "a51", "01")).method)

    def test_an_unknown_glyph_is_unresolved(self) -> None:
        self.assertIsNone(self.scratch.table({}).lookup(GlyphQuery("LASY9", "a51", "01")))

    def test_a_missing_table_is_empty(self) -> None:
        self.assertIsNone(IdentityTable(self.scratch.path / "absent.json").lookup(GlyphQuery("LASY9", "a51", "01")))

    def test_learning_writes_the_entry(self) -> None:
        table = IdentityTable(self.scratch.path / "learned.json")
        table.write(*table.entry_for("LASY9", "a51", Identity("◊", "worker")))
        self.assertEqual({"LASY9|a51": {"unicode": "◊", "method": "worker"}},
                         json.loads(table.path.read_text(encoding="utf-8")))

    def test_a_hex_code_is_stored_uppercase_in_the_code_key_space(self) -> None:
        key, _ = IdentityTable(self.scratch.path / "none.json").entry_for_code("MTEX", "0a", Identity("", "user"))
        self.assertEqual("MTEX|#0A", key)


class TestLearnCommand(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch = ScratchDirectory(self)
        self.default = self.scratch.path / "default.json"
        self.override = self.scratch.path / "override.json"
        self.learn = SilentCommand(FontCommands(identities_path=self.default).learn)

    def _entry(self, **extra) -> dict:
        return {"font": LASY9, "glyph": "a51", "unicode": "◊", "method": "user", "equals_sign": False, **extra}

    def test_the_table_option_redirects_the_write(self) -> None:
        self.learn.run(**self._entry(apply=True, table=str(self.override)))
        self.assertEqual((True, False), (self.override.is_file(), self.default.exists()))

    def test_without_the_option_the_constructor_table_is_written(self) -> None:
        self.learn.run(**self._entry(apply=True))
        self.assertTrue(self.default.is_file())

    def test_a_dry_run_writes_no_table(self) -> None:
        self.learn.run(**self._entry(apply=False))
        self.assertFalse(self.default.exists())


class TestIdentityResolver(unittest.TestCase):
    def test_a_self_identifying_glyph_name_bypasses_the_table(self) -> None:
        resolver = ScratchDirectory(self).resolver({"MinionPro|e.sc": {"unicode": "x", "method": "user"}})
        self.assertEqual(("e", METHOD_GLYPH_NAME), _as_pair(resolver.resolve(GlyphQuery("MinionPro", "e.sc", "01"))))

    def test_an_anonymous_glyph_falls_back_to_the_table(self) -> None:
        resolver = ScratchDirectory(self).resolver({"LASY9|a51": {"unicode": "◊", "method": "user"}})
        self.assertEqual(("◊", METHOD_TABLE), _as_pair(resolver.resolve(GlyphQuery("LASY9", "a51", "01"))))


def _as_pair(identity) -> tuple[str, str]:
    return identity.unicode, identity.method


class TestACodeEntryNeverAnswersForANamedGlyph(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch = ScratchDirectory(self)

    def _resolved(self, glyph_name: str | None) -> Identity | None:
        table = self.scratch.table({"Symbol|21": {"unicode": "→", "method": METHOD_TABLE}})
        return IdentityResolver(table).resolve(GlyphQuery("Symbol", glyph_name, "21", "\u00bc"))

    def test_a_font_that_names_the_glyph_ignores_the_code_entry(self) -> None:
        self.assertIsNone(self._resolved("onequarter.alt"))

    def test_a_font_that_names_no_glyph_takes_the_code_entry(self) -> None:
        self.assertEqual("→", self._resolved(None).unicode)


class TestIdentityKeyedByCharacter(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch = ScratchDirectory(self)
        self.table = self.scratch.table({"Palatino-Roman|U+00B4": {"unicode": "́", "method": "worker"}})

    def test_the_winansi_code_finds_the_entry(self) -> None:
        self.assertEqual("́", self.table.lookup(GlyphQuery("Palatino-Roman", None, "B4", "´")).unicode)

    def test_the_macroman_code_finds_the_same_entry(self) -> None:
        self.assertEqual("́", self.table.lookup(GlyphQuery("Palatino-Roman", None, "AB", "´")).unicode)

    def test_a_code_keyed_entry_still_wins_over_the_character(self) -> None:
        table = self.scratch.table({"Palatino-Roman|U+00B4": {"unicode": "́", "method": "worker"},
                                    "Palatino-Roman|AB": {"unicode": "«", "method": "user"}})
        self.assertEqual("«", table.lookup(GlyphQuery("Palatino-Roman", None, "AB", "´")).unicode)


if __name__ == "__main__":
    unittest.main()
