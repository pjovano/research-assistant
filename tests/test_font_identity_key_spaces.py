from __future__ import annotations

import argparse
import contextlib
import io
import json
import unittest

from _support import LiveTree

LiveTree.activate()

from _font_fixtures import ScratchDirectory, SilentCommand

from _clean.cli import ParserBuilder
from _clean.fontcommands import FontCommands
from _clean.glyphs import GlyphQuery, Identity, IdentityTable

FAMILY = "Fam"
GLYPH_NAMED_LIKE_A_CODE = "ae"
CODE = "AE"
NAMED_CHARACTER = "æ"
CODED_CHARACTER = "◊"
LEGACY_TABLE = {
    "Fam|0A": {"unicode": "x", "method": "user"},
    "Fam|A112": {"unicode": "y", "method": "worker"},
    "Fam|a51": {"unicode": "z", "method": "worker"},
    "Fam|U+00E6": {"unicode": "æ", "method": "user"},
    "Kin|01": {"unicode": "p", "method": "user"},
    "Kin|#01": {"unicode": "p", "method": "worker"},
    "Odd|02": {"unicode": "q", "method": "user"},
    "Odd|#02": {"unicode": "r", "method": "user"},
}
MIGRATED_TABLE = {
    "Fam|#0A": {"unicode": "x", "method": "user"},
    "Fam|A112": {"unicode": "y", "method": "worker"},
    "Fam|a51": {"unicode": "z", "method": "worker"},
    "Fam|U+00E6": {"unicode": "æ", "method": "user"},
    "Kin|#01": {"unicode": "p", "method": "worker"},
    "Odd|02": {"unicode": "q", "method": "user"},
    "Odd|#02": {"unicode": "r", "method": "user"},
}


class TestAGlyphNamedLikeACodeBesideThatCode(unittest.TestCase):
    def setUp(self) -> None:
        path = ScratchDirectory(self).path / "identities.json"
        named = IdentityTable(path)
        named.write(*named.entry_for(FAMILY, GLYPH_NAMED_LIKE_A_CODE, Identity(NAMED_CHARACTER, "user")))
        coded = IdentityTable(path)
        coded.write(*coded.entry_for_code(FAMILY, CODE, Identity(CODED_CHARACTER, "user")))
        self.table = IdentityTable(path)

    def test_the_glyph_name_resolves_to_its_own_entry(self) -> None:
        found = self.table.lookup(GlyphQuery(FAMILY, GLYPH_NAMED_LIKE_A_CODE, "01"))
        self.assertEqual(NAMED_CHARACTER, found.unicode)

    def test_the_nameless_code_resolves_to_its_own_entry(self) -> None:
        self.assertEqual(CODED_CHARACTER, self.table.lookup(GlyphQuery(FAMILY, None, CODE)).unicode)

    def test_the_two_entries_are_kept_under_two_keys(self) -> None:
        self.assertEqual({f"{FAMILY}|{GLYPH_NAMED_LIKE_A_CODE}", f"{FAMILY}|#{CODE}"},
                         set(json.loads(self.table.path.read_text(encoding="utf-8"))))


class TestTheKeySpaces(unittest.TestCase):
    def setUp(self) -> None:
        self.table = IdentityTable(ScratchDirectory(self).path / "none.json")

    def test_a_code_is_keyed_uppercase_in_the_code_space(self) -> None:
        key, _ = self.table.entry_for_code("MTEX", "0a", Identity("", "user"))
        self.assertEqual("MTEX|#0A", key)

    def test_a_glyph_name_is_keyed_as_written(self) -> None:
        key, _ = self.table.entry_for("MTEX", "ae", Identity("", "user"))
        self.assertEqual("MTEX|ae", key)


class TestLookupsDuringTheTransition(unittest.TestCase):
    def test_a_code_reads_its_legacy_unprefixed_entry(self) -> None:
        table = ScratchDirectory(self).table({"Fam|0A": {"unicode": "x", "method": "user"}})
        self.assertEqual("x", table.lookup(GlyphQuery("Fam", None, "0a")).unicode)

    def test_the_code_space_outranks_the_legacy_entry(self) -> None:
        table = ScratchDirectory(self).table({"Fam|0A": {"unicode": "x", "method": "user"},
                                              "Fam|#0A": {"unicode": "y", "method": "user"}})
        self.assertEqual("y", table.lookup(GlyphQuery("Fam", None, "0A")).unicode)

    def test_a_glyph_name_reads_the_entry_the_former_writer_folded_to_uppercase(self) -> None:
        table = ScratchDirectory(self).table({"Fam|A112": {"unicode": "x", "method": "user"}})
        self.assertEqual("x", table.lookup(GlyphQuery("Fam", "a112", "02")).unicode)


class MigrationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.table = ScratchDirectory(self).table(LEGACY_TABLE)
        self.migrate = SilentCommand(FontCommands(identities_path=self.table.path).migrate_keys)

    def on_disk(self) -> dict:
        return json.loads(self.table.path.read_text(encoding="utf-8"))


class TestTheReadOnlyMigration(MigrationTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.plan = json.loads(self.migrate.run(apply=False))

    def test_a_legacy_key_that_begins_with_a_digit_is_planned_into_the_code_space(self) -> None:
        self.assertEqual([{"from": "Fam|0A", "to": "Fam|#0A"}], self.plan["rewrites"])

    def test_a_legacy_key_that_may_be_a_glyph_name_is_reported_ambiguous(self) -> None:
        self.assertEqual(["Fam|A112"], [row["key"] for row in self.plan["ambiguous"]])

    def test_a_legacy_key_the_code_space_holds_with_the_same_character_is_planned_for_removal(self) -> None:
        self.assertEqual([{"from": "Kin|01", "to": "Kin|#01"}], self.plan["duplicates"])

    def test_a_legacy_key_the_code_space_holds_with_another_character_is_a_conflict(self) -> None:
        self.assertEqual(["Odd|02"], [row["from"] for row in self.plan["conflicts"]])

    def test_the_table_is_not_written(self) -> None:
        self.assertEqual(LEGACY_TABLE, self.on_disk())


class TestTheAppliedMigration(MigrationTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.migrate.run(apply=True)

    def test_the_table_holds_the_migrated_keys(self) -> None:
        self.assertEqual(MIGRATED_TABLE, self.on_disk())

    def test_a_second_run_plans_no_rewrite(self) -> None:
        plan = json.loads(self.migrate.run(apply=False))
        self.assertEqual(([], []), (plan["rewrites"], plan["duplicates"]))


class TestLearningACode(unittest.TestCase):
    def setUp(self) -> None:
        self.path = ScratchDirectory(self).path / "identities.json"
        self.learn = SilentCommand(FontCommands(identities_path=self.path).learn)

    def _learned_keys(self, glyph: str | None, code: str | None) -> set[str]:
        self.learn.run(font=FAMILY, glyph=glyph, code=code, unicode="x", method="user", equals_sign=False,
                       apply=True)
        return set(json.loads(self.path.read_text(encoding="utf-8")))

    def test_the_code_option_writes_the_code_key(self) -> None:
        self.assertEqual({f"{FAMILY}|#AE"}, self._learned_keys(None, "ae"))

    def test_the_glyph_option_writes_the_name_key_even_for_a_name_that_reads_as_hex(self) -> None:
        self.assertEqual({f"{FAMILY}|ae"}, self._learned_keys("ae", None))


class TestTheLearnCommandLine(unittest.TestCase):
    def _parsed(self, *arguments: str) -> argparse.Namespace:
        learn = ["fonts", "learn", "--font", FAMILY, "--unicode", "x", "--method", "user", *arguments]
        with contextlib.redirect_stderr(io.StringIO()):
            return ParserBuilder().build().parse_args(learn)

    def test_the_code_option_is_parsed_uppercase(self) -> None:
        self.assertEqual("AE", self._parsed("--code", "ae").code)

    def test_a_value_that_is_not_hex_is_refused_as_a_code(self) -> None:
        with self.assertRaises(SystemExit):
            self._parsed("--code", "a.sc")

    def test_the_glyph_and_the_code_options_exclude_each_other(self) -> None:
        with self.assertRaises(SystemExit):
            self._parsed("--glyph", "ae", "--code", "AE")

    def test_one_of_the_glyph_and_the_code_options_is_required(self) -> None:
        with self.assertRaises(SystemExit):
            self._parsed()


class TestTheMigrateKeysCommandLine(unittest.TestCase):
    def test_migrate_keys_is_a_fonts_subcommand_with_an_apply_form(self) -> None:
        parsed = ParserBuilder().build().parse_args(["fonts", "migrate-keys", "--apply"])
        self.assertTrue(parsed.apply)


if __name__ == "__main__":
    unittest.main()
