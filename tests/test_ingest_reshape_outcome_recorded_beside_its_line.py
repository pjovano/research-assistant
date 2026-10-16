from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _drive.script import ScriptRun, SkillScript
from _ingest.reshape import ReshapeDriver

LISTING_WITH_AN_AUTHOR = {"tree": [], "clusters": {"clusters": [], "findings": {}}, "authors": [{"author": "Kant"}]}
REPORT = {"created": ["Openings"], "moved": [], "folded": [{"name": "History of X", "into": "X"}],
          "questions": ["which root holds Openings?"]}


class RecordingScript(SkillScript):
    def __init__(self) -> None:
        super().__init__(Path("bibliographies.py"))

    def run(self, *args: str) -> ScriptRun:
        if args[0] == "shape-listing":
            Path(args[args.index("--out") + 1]).write_text(json.dumps(LISTING_WITH_AN_AUTHOR), encoding="utf-8")
            return ScriptRun(0, json.dumps({"parts": 1}))
        return ScriptRun(0, json.dumps(REPORT))


class TestTheReshapingRecordsItsOutcomeWhereTheClustersStepNamesIt(unittest.TestCase):
    def setUp(self) -> None:
        self.driver = ReshapeDriver(RecordingScript(), Path(tempfile.mkdtemp()))
        self.listed = self.driver.clusters()

    def reshaped(self) -> dict:
        answers = Path(self.listed["outcome"]).with_name("answers.json")
        answers.write_text("{}", encoding="utf-8")
        return self.driver.reshape(str(answers))

    def recorded(self) -> dict:
        return json.loads(Path(self.listed["outcome"]).read_text(encoding="utf-8"))

    def test_the_recorded_outcome_is_the_line_the_step_returns(self) -> None:
        self.assertEqual(self.reshaped(), self.recorded())

    def test_the_recorded_outcome_holds_every_fold(self) -> None:
        self.reshaped()
        self.assertEqual(REPORT["folded"], self.recorded()["folded"])

    def test_a_new_listing_clears_the_outcome_of_the_reshaping_before(self) -> None:
        self.reshaped()
        self.driver.clusters()
        self.assertFalse(Path(self.listed["outcome"]).exists())


if __name__ == "__main__":
    unittest.main()
