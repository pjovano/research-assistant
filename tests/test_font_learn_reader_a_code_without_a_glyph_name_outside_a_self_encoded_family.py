from __future__ import annotations

import json
import unittest

from _support import LiveTree

LiveTree.activate()

from _font_fixtures import ScratchDirectory, SilentCommand

from _clean.fontcommands import FontCommands
from _clean.readeranswers import MAX_UNRESOLVED_CODES

PDF = "chapter.pdf"
UNHASHED_FAMILY = "Baskerville-Regular"
HASHED_FAMILY = "AdvOT8608a8d1.B"
HEX_LETTERS_ONLY_FAMILY = "Facade"
TEX_FAMILY = "CMMI10"
GLYPH_NAME = "a51"


def code_of(number: int) -> str:
    return f"{number:02X}"


def identify_entry(font: str, code: str, glyph_name: str | None = None) -> dict:
    return {"font": font, "code": code, "glyph_name": glyph_name, "unicode": "U+007E"}


def answer(font: str, glyph: str, unicode: str = "∼") -> dict:
    return {"font": font, "glyph": glyph, "unicode": unicode, "evidence": "the render"}


class LearnReaderCase(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch = ScratchDirectory(self)
        self.table_path = self.scratch.path / "identities.json"
        self.commands = FontCommands(identities_path=self.table_path)

    def learn(self, codes: list[dict], answers: list[dict]) -> dict:
        report = self.write_json("identify.json", {"pdf": PDF, "codes": codes})
        output = SilentCommand(self.commands.learn_reader).run(
            answers=self.write_json("answers.json", {PDF: answers}), identify=[report], apply=True)
        return json.loads(output)

    def learn_one(self, font: str, unicode: str = "∼", glyph_name: str | None = None) -> dict:
        glyph = glyph_name or code_of(1)
        return self.learn([identify_entry(font, code_of(1), glyph_name)], [answer(font, glyph, unicode)])

    def write_json(self, name: str, payload: object):
        path = self.scratch.path / name
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def table(self) -> dict:
        return json.loads(self.table_path.read_text(encoding="utf-8")) if self.table_path.exists() else {}


class TestACodeWithoutAGlyphNameOutsideAFamilyFixingItsOwnEncoding(LearnReaderCase):
    def test_is_not_learned(self) -> None:
        self.learn_one(UNHASHED_FAMILY)
        self.assertEqual({}, self.table())

    def test_sets_the_pdf_aside_with_its_reason(self) -> None:
        rows = self.learn_one(UNHASHED_FAMILY)["set_aside"]
        self.assertEqual([(PDF, True)], [(row["pdf"], "outside a TeX family" in row["reason"]) for row in rows])

    def test_the_unchanged_shorthand_does_not_set_the_pdf_aside(self) -> None:
        self.assertEqual([], self.learn_one(UNHASHED_FAMILY, "=")["set_aside"])

    def test_the_unchanged_shorthand_is_not_learned(self) -> None:
        self.learn_one(UNHASHED_FAMILY, "=")
        self.assertEqual({}, self.table())

    def test_the_unchanged_shorthand_is_reported_as_needing_no_repair(self) -> None:
        plan = self.learn_one(UNHASHED_FAMILY, "=")
        self.assertEqual([code_of(1)], [row["glyph"] for row in plan["needs_no_repair"]])

    def test_a_family_ending_in_hex_letters_without_a_digit_carries_no_hash(self) -> None:
        self.assertEqual(1, len(self.learn_one(HEX_LETTERS_ONLY_FAMILY)["set_aside"]))


class TestACodeWithoutAGlyphNameInAFamilyFixingItsOwnEncoding(LearnReaderCase):
    def test_a_subset_hashed_family_with_a_style_suffix_is_learned(self) -> None:
        self.learn_one(HASHED_FAMILY)
        self.assertEqual("∼", self.table()[f"{HASHED_FAMILY}|#{code_of(1)}"]["unicode"])

    def test_a_tex_family_is_learned(self) -> None:
        self.learn_one(TEX_FAMILY)
        self.assertEqual("∼", self.table()[f"{TEX_FAMILY}|#{code_of(1)}"]["unicode"])


class TestANamedGlyphOutsideAFamilyFixingItsOwnEncoding(LearnReaderCase):
    def test_is_learned_under_its_name(self) -> None:
        self.learn_one(UNHASHED_FAMILY, glyph_name=GLYPH_NAME)
        self.assertEqual("∼", self.table()[f"{UNHASHED_FAMILY}|{GLYPH_NAME}"]["unicode"])


class TestThePdfsCountOfUnresolvedCodes(LearnReaderCase):
    def learn_codes(self, count: int) -> dict:
        codes = [identify_entry(TEX_FAMILY, code_of(number)) for number in range(1, count + 1)]
        return self.learn(codes, [answer(TEX_FAMILY, code["code"]) for code in codes])

    def test_more_than_the_limit_sets_every_answer_aside(self) -> None:
        plan = self.learn_codes(MAX_UNRESOLVED_CODES + 1)
        self.assertEqual((MAX_UNRESOLVED_CODES + 1, {}), (len(plan["set_aside"]), self.table()))

    def test_the_limit_itself_is_learned(self) -> None:
        self.assertEqual(MAX_UNRESOLVED_CODES, len(self.learn_codes(MAX_UNRESOLVED_CODES)["learn"]))


if __name__ == "__main__":
    unittest.main()
