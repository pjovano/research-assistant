from __future__ import annotations

import json
import unittest

from _support import LiveTree

LiveTree.activate()

from _font_fixtures import ScratchDirectory, SilentCommand

from _clean.fontcommands import FontCommands
from _clean.readeranswers import LearnRefused

PDF = "chapter.pdf"
SECOND_PDF = "other chapter.pdf"
HEADING_FONT = "AdvOTabc123"
LETTER_A_CODE = "61"
TILDE_CODE = "7E"


def identify_entry(code: str, current: str, glyph_name: str | None = None) -> dict:
    return {"font": HEADING_FONT, "code": code, "glyph_name": glyph_name, "unicode": current}


def answer(glyph: str, unicode: str) -> dict:
    return {"font": HEADING_FONT, "glyph": glyph, "unicode": unicode, "evidence": "the render"}


class LearnReaderTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch = ScratchDirectory(self)
        self.table_path = self.scratch.path / "identities.json"
        self.commands = FontCommands(identities_path=self.table_path)

    def write_json(self, name: str, payload: object) -> str:
        path = self.scratch.path / name
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def identify_report(self, pdf: str, codes: list[dict]) -> str:
        return self.write_json(f"{pdf}.identify.json", {"pdf": pdf, "codes": codes})

    def learn_reader(self, answers: object, reports: list, apply: bool = True) -> dict:
        output = SilentCommand(self.commands.learn_reader).run(
            answers=self.write_json("answers.json", answers), identify=reports, apply=apply)
        return json.loads(output)

    def table(self) -> dict:
        return json.loads(self.table_path.read_text(encoding="utf-8")) if self.table_path.exists() else {}

    def seed_table(self, entries: dict) -> None:
        self.table_path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")


class TestTheShorthandLearnsTheCharacterEmittedToday(LearnReaderTestCase):
    def setUp(self) -> None:
        super().setUp()
        report = self.identify_report(PDF, [identify_entry(LETTER_A_CODE, "U+0061")])
        self.learn_reader({PDF: [answer(LETTER_A_CODE, "=")]}, [report])

    def test_the_entry_under_the_code_key_holds_the_current_character(self) -> None:
        self.assertEqual("a", self.table()[f"{HEADING_FONT}|#{LETTER_A_CODE}"]["unicode"])

    def test_the_entry_under_the_code_key_is_learned_by_the_worker(self) -> None:
        self.assertEqual("worker", self.table()[f"{HEADING_FONT}|#{LETTER_A_CODE}"]["method"])


class TestANamedCharacterIsLearnedAsGiven(LearnReaderTestCase):
    def test_the_entry_under_the_code_key_holds_the_named_character(self) -> None:
        report = self.identify_report(PDF, [identify_entry(TILDE_CODE, "U+003D")])
        self.learn_reader({PDF: [answer(TILDE_CODE, "~")]}, [report])
        self.assertEqual("~", self.table()[f"{HEADING_FONT}|#{TILDE_CODE}"]["unicode"])


class TestAPlainListBelongsToItsOnlyReport(LearnReaderTestCase):
    def test_the_list_resolves_against_the_single_report_into_the_code_key(self) -> None:
        report = self.identify_report(PDF, [identify_entry(LETTER_A_CODE, "U+0061")])
        self.learn_reader([answer(LETTER_A_CODE, "=")], [report])
        self.assertEqual("a", self.table()[f"{HEADING_FONT}|#{LETTER_A_CODE}"]["unicode"])

    def test_a_list_against_two_reports_is_refused(self) -> None:
        reports = [self.identify_report(pdf, [identify_entry(LETTER_A_CODE, "U+0061")]) for pdf in (PDF, SECOND_PDF)]
        with self.assertRaises(LearnRefused):
            self.learn_reader([answer(LETTER_A_CODE, "=")], reports)


class TestAnswersTheTableCannotTake(LearnReaderTestCase):
    def test_an_unresolved_glyph_is_listed_and_not_learned(self) -> None:
        report = self.identify_report(PDF, [identify_entry(LETTER_A_CODE, "U+0061")])
        plan = self.learn_reader({PDF: [answer(LETTER_A_CODE, "unresolved")]}, [report])
        self.assertEqual((1, {}), (len(plan["unresolved"]), self.table()))

    def test_a_differing_table_entry_is_a_conflict_and_is_kept(self) -> None:
        self.seed_table({f"{HEADING_FONT}|{LETTER_A_CODE}": {"unicode": "α", "method": "user"}})
        report = self.identify_report(PDF, [identify_entry(LETTER_A_CODE, "U+0061")])
        plan = self.learn_reader({PDF: [answer(LETTER_A_CODE, "=")]}, [report])
        self.assertEqual((1, "α"), (len(plan["conflicts"]), self.table()[f"{HEADING_FONT}|{LETTER_A_CODE}"]["unicode"]))

    def test_an_answer_no_report_names_is_refused(self) -> None:
        report = self.identify_report(PDF, [identify_entry(LETTER_A_CODE, "U+0061")])
        with self.assertRaises(LearnRefused):
            self.learn_reader({PDF: [answer(TILDE_CODE, "=")]}, [report])

    def test_a_dry_run_writes_no_table(self) -> None:
        report = self.identify_report(PDF, [identify_entry(LETTER_A_CODE, "U+0061")])
        self.learn_reader({PDF: [answer(LETTER_A_CODE, "=")]}, [report], apply=False)
        self.assertFalse(self.table_path.exists())


class TestTheSingleEntryFormRefusesTheShorthand(LearnReaderTestCase):
    def learn_equals(self, equals_sign: bool) -> None:
        SilentCommand(self.commands.learn).run(font=HEADING_FONT, glyph="3D", unicode="=", method="worker",
                                               equals_sign=equals_sign, apply=True)

    def test_a_bare_equals_is_refused_and_writes_nothing(self) -> None:
        with self.assertRaises(LearnRefused):
            self.learn_equals(equals_sign=False)
        self.assertFalse(self.table_path.exists())

    def test_an_equals_sign_marked_as_one_is_learned_literally(self) -> None:
        self.learn_equals(equals_sign=True)
        self.assertEqual("=", self.table()[f"{HEADING_FONT}|3D"]["unicode"])


if __name__ == "__main__":
    unittest.main()
