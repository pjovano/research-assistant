from __future__ import annotations

import json
import unittest

from _support import LiveTree

LiveTree.activate()

from _font_fixtures import ScratchDirectory, SilentCommand

from _clean.fontcommands import FontCommands

FIRST_PDF = "first.pdf"
SECOND_PDF = "second.pdf"
SELF_ENCODED_FAMILY = "CMSY10"
RE_ENCODED_FAMILY = "TimesNewRomanPSMT"
CODE = "7E"
GLYPH_NAME = "a51"


def identify_entry(font: str, glyph_name: str | None = None) -> dict:
    return {"font": font, "code": CODE, "glyph_name": glyph_name, "unicode": "U+007E"}


def answer(font: str, glyph: str, unicode: str) -> dict:
    return {"font": font, "glyph": glyph, "unicode": unicode, "evidence": "the render"}


class ReaderLearningTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch = ScratchDirectory(self)
        self.table_path = self.scratch.path / "identities.json"
        self.commands = FontCommands(identities_path=self.table_path)

    def write_json(self, name: str, payload: object) -> str:
        path = self.scratch.path / name
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def learn_reader(self, answers: dict, codes: dict[str, list[dict]]) -> dict:
        reports = [self.write_json(f"{pdf}.identify.json", {"pdf": pdf, "codes": listed})
                   for pdf, listed in codes.items()]
        output = SilentCommand(self.commands.learn_reader).run(
            answers=self.write_json("answers.json", answers), identify=reports, apply=True)
        return json.loads(output)

    def table(self) -> dict:
        return json.loads(self.table_path.read_text(encoding="utf-8")) if self.table_path.exists() else {}


class TestTwoAnswersGivingOneKeyDifferentCharacters(ReaderLearningTestCase):
    def setUp(self) -> None:
        super().setUp()
        codes = {pdf: [identify_entry(SELF_ENCODED_FAMILY)] for pdf in (FIRST_PDF, SECOND_PDF)}
        self.plan = self.learn_reader({FIRST_PDF: [answer(SELF_ENCODED_FAMILY, CODE, "∼")],
                                       SECOND_PDF: [answer(SELF_ENCODED_FAMILY, CODE, "≈")]}, codes)

    def test_neither_character_is_learned(self) -> None:
        self.assertEqual({}, self.table())

    def test_both_answers_are_reported_as_conflicts(self) -> None:
        self.assertEqual({"∼", "≈"}, {row["unicode"] for row in self.plan["conflicts"]})


class TestTwoAnswersGivingOneKeyTheSameCharacter(ReaderLearningTestCase):
    def test_the_code_key_is_learned_once(self) -> None:
        codes = {pdf: [identify_entry(SELF_ENCODED_FAMILY)] for pdf in (FIRST_PDF, SECOND_PDF)}
        plan = self.learn_reader({FIRST_PDF: [answer(SELF_ENCODED_FAMILY, CODE, "∼")],
                                  SECOND_PDF: [answer(SELF_ENCODED_FAMILY, CODE, "∼")]}, codes)
        self.assertEqual((1, "∼"), (len(plan["learn"]), self.table()[f"{SELF_ENCODED_FAMILY}|#{CODE}"]["unicode"]))


class TestACodeWithoutAGlyphNameInAFamilyReEncodedPerDocument(ReaderLearningTestCase):
    def learn_one(self, unicode: str) -> dict:
        return self.learn_reader({FIRST_PDF: [answer(RE_ENCODED_FAMILY, CODE, unicode)]},
                                 {FIRST_PDF: [identify_entry(RE_ENCODED_FAMILY)]})

    def test_another_character_is_not_learned(self) -> None:
        self.learn_one("∼")
        self.assertEqual({}, self.table())

    def test_another_character_sets_the_pdf_aside(self) -> None:
        self.assertEqual([FIRST_PDF], [row["pdf"] for row in self.learn_one("∼")["set_aside"]])

    def test_the_unchanged_shorthand_is_not_learned(self) -> None:
        self.learn_one("=")
        self.assertEqual({}, self.table())

    def test_the_unchanged_shorthand_is_reported_as_needing_no_repair(self) -> None:
        self.assertEqual([CODE], [row["glyph"] for row in self.learn_one("=")["needs_no_repair"]])


class TestANamedGlyphInAFamilyReEncodedPerDocument(ReaderLearningTestCase):
    def test_the_named_glyph_is_learned(self) -> None:
        self.learn_reader({FIRST_PDF: [answer(RE_ENCODED_FAMILY, GLYPH_NAME, "∼")]},
                          {FIRST_PDF: [identify_entry(RE_ENCODED_FAMILY, GLYPH_NAME)]})
        self.assertEqual("∼", self.table()[f"{RE_ENCODED_FAMILY}|{GLYPH_NAME}"]["unicode"])


class TestACodeWithoutAGlyphNameInAFamilyFixingItsOwnEncoding(ReaderLearningTestCase):
    def test_the_code_is_learned_under_the_code_key(self) -> None:
        self.learn_reader({FIRST_PDF: [answer(SELF_ENCODED_FAMILY, CODE, "∼")]},
                          {FIRST_PDF: [identify_entry(SELF_ENCODED_FAMILY)]})
        self.assertEqual("∼", self.table()[f"{SELF_ENCODED_FAMILY}|#{CODE}"]["unicode"])


if __name__ == "__main__":
    unittest.main()
