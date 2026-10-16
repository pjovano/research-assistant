from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _drive.script import ScriptRun, SkillScript
from _ingest.reshape import ReshapeDriver, TouchedFile

EMPTY_LISTING = {"tree": [], "clusters": {"clusters": [], "findings": {"new": [], "split": [], "misfit": [],
                                                                        "missing": []}},
                 "authors": [], "nominations": [], "descriptions": {}}
REPORT = {"created": ["Openings"], "moved": [], "touched": ["Logic", "Openings"], "works": ["A - 2000 - B"],
          "questions": ["three works gathered on nothing"], "applied": True}
PARTS_CUT = 3


class ListingScript(SkillScript):
    def __init__(self, listing: dict, reshape: ScriptRun | None = None, merge: ScriptRun | None = None) -> None:
        super().__init__(Path("bibliographies.py"))
        self._listing = listing
        self._reshape = reshape or ScriptRun(0, json.dumps(REPORT))
        self._merge = merge or ScriptRun(0, json.dumps({"parts": PARTS_CUT, "answered": PARTS_CUT}))
        self.calls: list[tuple[str, ...]] = []

    def run(self, *args: str) -> ScriptRun:
        self.calls.append(args)
        if args[0] == "shape-listing":
            Path(args[args.index("--out") + 1]).write_text(json.dumps(self._listing), encoding="utf-8")
            return ScriptRun(0, json.dumps({"parts": PARTS_CUT}))
        return self._merge if args[0] == "merge-answers" else self._reshape


class ReshapeDriverCase(unittest.TestCase):
    def setUp(self) -> None:
        self.works_dir = Path(tempfile.mkdtemp())

    def driver(self, listing: dict = EMPTY_LISTING, reshape: ScriptRun | None = None,
               merge: ScriptRun | None = None) -> ReshapeDriver:
        self.script = ListingScript(listing, reshape, merge)
        return ReshapeDriver(self.script, self.works_dir)


class TestTheClustersStep(ReshapeDriverCase):
    def test_a_listing_with_nothing_to_shape_is_nothing(self) -> None:
        self.assertEqual({"state": "nothing"}, self.driver().clusters())

    def test_a_new_finding_asks_the_shaper(self) -> None:
        listing = {**EMPTY_LISTING, "clusters": {"clusters": [], "findings": {"new": [{"cluster": 1, "works": []}],
                                                                               "split": [], "misfit": [], "missing": []}}}
        line = self.driver(listing).clusters()
        self.assertEqual("shape", line["state"])
        self.assertTrue(line["dir"].endswith("/reshape/parts"))
        self.assertEqual({"count": PARTS_CUT, "listing": "{n}/listing.json", "answers": "{n}/answers.json"},
                         line["parts"])

    def test_the_listing_is_cut_into_parts_beside_the_whole(self) -> None:
        self.driver().clusters()
        cut = self.script.calls[0]
        self.assertEqual(str(self.works_dir / "reshape" / "parts"), cut[cut.index("--parts") + 1])

    def test_a_new_listing_clears_the_merged_answers_of_the_reshaping_before(self) -> None:
        answers = self.works_dir / "reshape" / "answers.json"
        answers.parent.mkdir(parents=True)
        answers.write_text("{}", encoding="utf-8")
        self.driver().clusters()
        self.assertFalse(answers.exists())

    def test_an_uncovered_author_or_a_nomination_asks_the_shaper(self) -> None:
        self.assertEqual("shape", self.driver({**EMPTY_LISTING, "authors": [{"author": "Kant"}]}).clusters()["state"])
        self.assertEqual("shape", self.driver({**EMPTY_LISTING, "nominations": [{"name": "X"}]}).clusters()["state"])

    def test_a_subtopic_listed_by_an_author_alone_asks_the_shaper(self) -> None:
        listing = {**EMPTY_LISTING, "unlinked_subtopics": [{"name": "Kant's Logic", "parents": ["Kant"]}]}
        self.assertEqual("shape", self.driver(listing).clusters()["state"])

    def test_a_routing_placement_asks_the_shaper(self) -> None:
        listing = {**EMPTY_LISTING, "routing_placements": [{"work": "W", "on": "Kant", "maps": ["Kant's Logic"]}]}
        self.assertEqual("shape", self.driver(listing).clusters()["state"])

    def test_a_fold_candidate_asks_the_shaper(self) -> None:
        listing = {**EMPTY_LISTING, "fold_candidates": [{"narrower": "Responses to X", "broader": "X"}]}
        self.assertEqual("shape", self.driver(listing).clusters()["state"])

    def test_the_batchs_nominations_file_is_handed_to_the_listing(self) -> None:
        self.driver().clusters()
        self.assertIn(str(self.works_dir / "nominations.json"), self.script.calls[0])

    def test_a_failed_listing_halts(self) -> None:
        script = ListingScript(EMPTY_LISTING)
        script.run = lambda *args: ScriptRun(1, "boom")
        self.assertEqual("halt", ReshapeDriver(script, self.works_dir).clusters()["state"])


class TestTheMergeStep(ReshapeDriverCase):
    def test_the_parts_answers_are_merged_into_the_answers_file_the_reshape_reads(self) -> None:
        line = self.driver().merge()
        answers = str(self.works_dir / "reshape" / "answers.json")
        self.assertEqual({"state": "merged", "answers": answers, "parts": PARTS_CUT, "answered": PARTS_CUT}, line)
        self.assertEqual(("merge-answers", "--parts", str(self.works_dir / "reshape" / "parts"), "--out", answers),
                         self.script.calls[-1])

    def test_no_answered_part_sets_the_reshaping_aside(self) -> None:
        unanswered = ScriptRun(0, json.dumps({"parts": PARTS_CUT, "answered": 0}))
        self.assertEqual("aside", self.driver(merge=unanswered).merge()["state"])

    def test_a_failed_merge_sets_the_reshaping_aside(self) -> None:
        line = self.driver(merge=ScriptRun(1, "boom")).merge()
        self.assertEqual(("aside", True), (line["state"], "boom" in line["question"]))


class TestTheReshapeStep(ReshapeDriverCase):
    def answers(self) -> Path:
        path = self.works_dir / "reshape" / "answers.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"create": [], "move": [], "questions": []}), encoding="utf-8")
        return path

    def test_the_answers_are_applied_and_the_report_carried(self) -> None:
        line = self.driver().reshape(str(self.answers()))
        self.assertEqual({"state": "reshaped", "created": ["Openings"], "moved": [], "linked": [], "unlinked": [],
                          "added": [], "folded": [], "questions": ["three works gathered on nothing"]}, line)
        self.assertEqual(("reshape", "--answers", str(self.works_dir / "reshape" / "answers.json"), "--apply"),
                         self.script.calls[-1])

    def test_the_touched_bibliographies_and_works_are_recorded_for_the_glosses(self) -> None:
        self.driver().reshape(str(self.answers()))
        touched = TouchedFile(self.works_dir / "reshape" / "touched.json").read()
        self.assertEqual({"bibliographies": ["Logic", "Openings"], "works": ["A - 2000 - B"]}, touched)

    def test_no_answers_file_sets_the_reshaping_aside(self) -> None:
        line = self.driver().reshape(str(self.works_dir / "reshape" / "answers.json"))
        self.assertEqual("aside", line["state"])

    def test_refused_answers_set_the_reshaping_aside_with_the_refusal(self) -> None:
        refused = ScriptRun(5, json.dumps({"refused": "'Logic' is no new name"}))
        line = self.driver(reshape=refused).reshape(str(self.answers()))
        self.assertEqual("aside", line["state"])
        self.assertIn("no new name", line["question"])


if __name__ == "__main__":
    unittest.main()
