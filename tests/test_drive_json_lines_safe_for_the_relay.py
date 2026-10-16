from __future__ import annotations

import contextlib
import io
import json
import unittest

from _support import LiveTree

LiveTree.activate()

from _drive.steps import JsonLine

PATH = "/Users/someone/.research-vault/cache/ingest/by-key/7/scope-verdicts-0.json"


def printed(outcome: dict) -> str:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        JsonLine.emit(outcome)
    return output.getvalue()


def emitted(outcome: dict) -> dict:
    return json.loads(printed(outcome))


class TestAJsonLineCarriesNoCharacterTheRelayTurnsIntoADelimiter(unittest.TestCase):
    def test_a_curly_quotation_mark_becomes_an_apostrophe(self) -> None:
        self.assertEqual("'Allgemeines Dreieck' in 'Locke'", emitted({"q": "„Allgemeines Dreieck“ in “Locke”"})["q"])

    def test_a_straight_quotation_mark_becomes_an_apostrophe(self) -> None:
        self.assertEqual("the 'title'", emitted({"q": 'the "title"'})["q"])

    def test_a_backslash_becomes_a_slash(self) -> None:
        self.assertEqual("a/b", emitted({"q": "a\\b"})["q"])

    def test_a_line_break_becomes_a_space(self) -> None:
        self.assertEqual("one two", emitted({"q": "one\ntwo"})["q"])

    def test_the_line_is_one_line(self) -> None:
        self.assertEqual(1, len(printed({"q": "one\ntwo\r\nthree"}).splitlines()))

    def test_a_path_is_kept(self) -> None:
        self.assertEqual(PATH, emitted({"verdicts": PATH})["verdicts"])

    def test_an_accented_letter_is_kept_unescaped(self) -> None:
        self.assertIn("Phénoménologie", printed({"pdf": "Benoist - 1997 - Phénoménologie.pdf"}))

    def test_nested_values_are_made_safe(self) -> None:
        outcome = {"groups": [{"codes": "x“y", "answers": PATH}], "notes": ["a\\b"]}
        self.assertEqual({"groups": [{"codes": "x'y", "answers": PATH}], "notes": ["a/b"]}, emitted(outcome))

    def test_numbers_and_booleans_are_kept(self) -> None:
        self.assertEqual({"key": 7, "ok": True, "none": None}, emitted({"key": 7, "ok": True, "none": None}))


if __name__ == "__main__":
    unittest.main()
