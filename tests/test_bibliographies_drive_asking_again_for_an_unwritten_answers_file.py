from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

import vault
from _bibliographies.drive import ClassifyDriver
from _bibliography_fixtures import HOULGATE
from test_bibliographies_drive import ClassifyCase


class TestAnAnswersFileTheClassifierNeverWrote(ClassifyCase):
    def classify_without_answers(self) -> dict:
        missing = vault.BIBLIOGRAPHIES_DIR.parent / "answers.json"
        return ClassifyDriver(self.place).classify(HOULGATE, missing)

    def test_the_classifier_is_asked_again(self) -> None:
        self.assertEqual("unwritten", self.classify_without_answers()["state"])

    def test_an_unreadable_answers_file_still_sets_the_work_aside(self) -> None:
        path = vault.BIBLIOGRAPHIES_DIR.parent / "answers.json"
        path.write_text("not json", encoding="utf-8")
        self.assertEqual("aside", ClassifyDriver(self.place).classify(HOULGATE, path)["state"])


if __name__ == "__main__":
    unittest.main()
