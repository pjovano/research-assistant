from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from unittest import mock

from _support import LiveTree

LiveTree.activate()

import bibliographies
import vault
from _bibliographies.drive import BibliographiesScript, ClassifyDriver
from _bibliography_fixtures import HOULGATE, TemporaryVault
from _drive.script import ScriptRun

PLACED_BEFORE_STAGE_FOUR = {"title": "The Opening of Hegel's Logic", "author": ["Houlgate"], "year": 2006,
                            "source_type": None, "source_role": None, "field": ["[[Hegel]]"]}
ANSWERS = {"source_type": "monograph", "source_role": "secondary", "field": ["Logic"], "questions": []}


class StubPlace(BibliographiesScript):
    def run(self, *args: str) -> ScriptRun:
        return ScriptRun(0, json.dumps({"bibliographies": ["Logic"], "applied": True}))


class PlacedBeforeStageFourCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TemporaryVault(self)
        self.vault.bibliography("Logic")
        self.vault.bibliography("Hegel")
        self.vault.note(HOULGATE, **PLACED_BEFORE_STAGE_FOUR)

    def opening_exit_code(self) -> int:
        with contextlib.redirect_stdout(io.StringIO()), \
                mock.patch.object(sys, "argv", ["bibliographies.py", "opening", HOULGATE]):
            try:
                bibliographies.CommandLine().run()
            except SystemExit as stopped:
                return stopped.code
        return 0

    def classified(self) -> dict:
        path = vault.BIBLIOGRAPHIES_DIR.parent / "answers.json"
        path.write_text(json.dumps(ANSWERS), encoding="utf-8")
        return ClassifyDriver(StubPlace()).classify(HOULGATE, path)

    def meta(self) -> dict:
        return vault.read_frontmatter(vault.held_note_path(HOULGATE))[0]


class TestACorpusFilePlacedBeforeStageFour(PlacedBeforeStageFourCase):
    def test_its_opening_reports_it_unclassified(self) -> None:
        self.assertEqual(0, self.opening_exit_code())

    def test_stage_four_classifies_it(self) -> None:
        self.classified()
        self.assertEqual(("monograph", "secondary"), (self.meta()["source_type"], self.meta()["source_role"]))

    def test_stage_four_keeps_the_bibliography_that_placed_it_beside_its_own(self) -> None:
        self.classified()
        self.assertEqual(["Hegel", "Logic"], vault.field_topics(self.meta()))

    def test_the_same_answers_given_again_match_the_written_classification(self) -> None:
        self.classified()
        self.assertNotEqual("aside", self.classified()["state"])


if __name__ == "__main__":
    unittest.main()
