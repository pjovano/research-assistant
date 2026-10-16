from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _drive.script import ScriptRun, SkillScript
from _drive.steps import BoundedOutcome
from _drive.work import ListedWorks
from _ingest.glosses import GlossDriver

HEGEL_PDF = "Hegel - 1969 - Wissenschaft der Logik.pdf"
LOGIC = "Logic"
ETHICS = "Ethics"
MANY_BIBLIOGRAPHIES = 400


def json_run(payload: object, returncode: int = 0) -> ScriptRun:
    return ScriptRun(returncode, json.dumps(payload))


def planned(*names: str) -> ScriptRun:
    return json_run({"bibliographies": list(names)})


class StubBibliographies(SkillScript):
    def __init__(self, **replies: ScriptRun) -> None:
        super().__init__(Path("bibliographies.py"))
        self._replies = {"gloss-copy": json_run({"changed": [], "applied": True}), "gloss-plan": planned(LOGIC, ETHICS),
                         "gloss-listing": ScriptRun(0, ""), "gloss-write": json_run({"problems": []}),
                         **{command.replace("_", "-"): run for command, run in replies.items()}}
        self.calls: list[tuple[str, ...]] = []

    def run(self, *args: str) -> ScriptRun:
        self.calls.append(args)
        return self._replies[args[0]]

    def calls_of(self, command: str) -> list[tuple[str, ...]]:
        return [call for call in self.calls if call[0] == command]


class GlossDriverCase(unittest.TestCase):
    def setUp(self) -> None:
        self.works_dir = Path(tempfile.mkdtemp())
        ListedWorks(self.works_dir).list(1, HEGEL_PDF)
        self.stubbed()

    def stubbed(self, **replies: ScriptRun) -> None:
        self.script = StubBibliographies(**replies)
        self.driver = GlossDriver(self.script, self.works_dir)

    def directory(self) -> Path:
        return Path(self.driver.plan(["1"], False)["root"]) / "1"

    def answered(self) -> Path:
        directory = self.directory()
        (directory / "answers.json").write_text('{"introduction": "Works on logic."}', encoding="utf-8")
        return directory


class TestThePlanStep(GlossDriverCase):
    def test_the_descriptions_are_copied_before_anything_is_planned(self) -> None:
        self.driver.plan(["1"], False)
        self.assertEqual([("gloss-copy", "--apply"), "gloss-plan"], [self.script.calls[0], self.script.calls[1][0]])

    def test_the_keyed_works_basenames_are_passed_to_the_plan(self) -> None:
        self.driver.plan(["1"], False)
        self.assertEqual([("gloss-plan", "--works", "Hegel - 1969 - Wissenschaft der Logik", "--bibliographies")],
                         self.script.calls_of("gloss-plan"))

    def test_all_asks_the_plan_for_every_bibliography(self) -> None:
        self.driver.plan([], True)
        self.assertEqual([("gloss-plan", "--all")], self.script.calls_of("gloss-plan"))

    def test_the_line_names_the_root_and_the_count_of_bibliographies(self) -> None:
        line = self.driver.plan(["1"], False)
        self.assertEqual(("gloss", 2, str(self.works_dir / "glosses")), (line["state"], line["count"], line["root"]))

    def test_each_bibliography_gets_a_numbered_directory_naming_it(self) -> None:
        root = self.directory().parent
        names = [json.loads((root / number / "plan.json").read_text(encoding="utf-8"))["name"] for number in "12"]
        self.assertEqual([LOGIC, ETHICS], names)

    def test_a_listing_is_requested_for_each_bibliography_into_its_directory(self) -> None:
        root = self.directory().parent
        self.assertEqual([("gloss-listing", LOGIC, "--out", str(root / "1" / "listing.json")),
                          ("gloss-listing", ETHICS, "--out", str(root / "2" / "listing.json"))],
                         self.script.calls_of("gloss-listing"))

    def test_a_plan_of_many_bibliographies_fits_one_line_unspilled(self) -> None:
        self.stubbed(gloss_plan=planned(*(f"{LOGIC} {number}" for number in range(MANY_BIBLIOGRAPHIES))))
        line = self.driver.plan([], True)
        self.assertEqual(MANY_BIBLIOGRAPHIES, BoundedOutcome(line, self.works_dir / "spilled").of()["count"])

    def test_the_directories_of_an_earlier_plan_are_cleared(self) -> None:
        root = self.directory().parent
        self.stubbed(gloss_plan=planned(LOGIC))
        self.driver.plan(["1"], False)
        self.assertEqual(["1"], sorted(child.name for child in root.iterdir()))

    def test_nothing_planned_is_nothing(self) -> None:
        self.stubbed(gloss_plan=planned())
        self.assertEqual({"state": "nothing"}, self.driver.plan(["1"], False))

    def test_a_failed_copy_halts_the_step(self) -> None:
        self.stubbed(gloss_copy=ScriptRun(1, "a conflict copy"))
        self.assertEqual("halt", self.driver.plan(["1"], False)["state"])


class TestTheFinishStep(GlossDriverCase):
    def test_the_answers_are_written_into_the_bibliography_the_directory_names(self) -> None:
        directory = self.answered()
        line = self.driver.finish(str(directory))
        self.assertEqual({"state": "glossed", "bibliography": LOGIC}, line)
        self.assertEqual(("gloss-write", LOGIC, "--answers", str(directory / "answers.json")), self.script.calls[-1])

    def test_no_answers_file_sets_the_bibliography_aside(self) -> None:
        line = self.driver.finish(str(self.directory()))
        self.assertEqual("aside", line["state"])
        self.assertIn("wrote no answers file", line["question"])

    def test_refused_answers_set_the_bibliography_aside_with_the_problems(self) -> None:
        directory = self.answered()
        self.script._replies["gloss-write"] = json_run({"problems": ["the introduction is empty"]}, 1)
        line = self.driver.finish(str(directory))
        self.assertEqual("aside", line["state"])
        self.assertIn("the introduction is empty", line["question"])


if __name__ == "__main__":
    unittest.main()
