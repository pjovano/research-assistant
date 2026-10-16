from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _drive.steps import LINE_LIMIT, JsonLine
from _vaults import TempVault

QUESTION = "confirm or reject the link from Someone - 2019 - A Work: {'entry': 'Other, A. 2001. A Title.', 'score': 74.0}"
MANY = 700


def printed(outcome: dict) -> str:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        JsonLine.emit(outcome)
    return output.getvalue()


class TestAJsonLineLongerThanTheRelayReturnsSpillsItsLongestListToAFile(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault().activate()
        self.addCleanup(self.vault.discard)
        self.questions = [f"{QUESTION} {index}" for index in range(MANY)]

    def emitted(self) -> dict:
        return json.loads(printed({"state": "linked", "linked": ["A"], "questions": self.questions}))

    def spill_path(self) -> Path:
        pointer = self.emitted()["questions"][0]
        return Path(pointer.split(" in ", 1)[1])

    def test_the_line_fits_the_limit(self) -> None:
        self.assertLessEqual(len(printed({"state": "linked", "questions": self.questions}).strip()), LINE_LIMIT)

    def test_the_spilled_list_becomes_one_line_naming_its_count_and_file(self) -> None:
        self.assertTrue(self.emitted()["questions"][0].startswith(f"{MANY} questions, one to a line, in "))

    def test_the_file_holds_every_item_one_to_a_line(self) -> None:
        self.assertEqual(self.questions, self.spill_path().read_text(encoding="utf-8").splitlines())

    def test_the_state_and_a_short_list_are_kept(self) -> None:
        emitted = self.emitted()
        self.assertEqual(("linked", ["A"]), (emitted["state"], emitted["linked"]))

    def test_a_line_within_the_limit_is_unchanged(self) -> None:
        self.assertEqual({"state": "linked", "questions": [QUESTION]},
                         json.loads(printed({"state": "linked", "questions": [QUESTION]})))


if __name__ == "__main__":
    unittest.main()
