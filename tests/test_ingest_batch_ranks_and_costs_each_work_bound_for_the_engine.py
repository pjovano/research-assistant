from __future__ import annotations

import json
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _drive.script import ScriptRun, SkillScript
from _drive.steps import StepGuard
from _ingest.selection import EngineWorkCosts

ARTICLE_FROM_PIXELS = "article.pdf"
LONG_TEXT_LAYER_BOOK = "Doe - 2020 - A Long Book"
UNOPENED = "Broken - 2001 - Torn"
CLASSIFIED_LATER = "Roe - 2019 - Another Work"
COSTS = {ARTICLE_FROM_PIXELS: [20, 20], f"{LONG_TEXT_LAYER_BOOK}.pdf": [0, 900], f"{UNOPENED}.pdf": None}


class CostsScript(SkillScript):
    def __init__(self, costs: dict | None) -> None:
        super().__init__(Path("extract.py"))
        self._costs = costs
        self.asked: list[tuple[str, ...]] = []

    def run(self, *args: str) -> ScriptRun:
        self.asked.append(args)
        if self._costs is None:
            return ScriptRun(1, "", "Traceback: the costs failed")
        return ScriptRun(0, json.dumps({"state": "costed", "costs": {pdf: self._costs[pdf] for pdf in args[1:]}}))


def works() -> list[dict]:
    return [{"key": 1, "pdf": ARTICLE_FROM_PIXELS, "from": "clean"},
            {"key": 2, "basename": CLASSIFIED_LATER, "from": "cite"},
            {"key": 3, "basename": UNOPENED, "from": "extract"},
            {"key": 4, "basename": LONG_TEXT_LAYER_BOOK, "from": "extract"}]


def names(listed: list[dict]) -> list[str]:
    return [work.get("pdf") or work["basename"] for work in listed]


class TestTheBatchRanksEachWorkBoundForTheEngine(unittest.TestCase):
    def test_works_bound_for_the_engine_come_cheapest_first_and_the_rest_after(self) -> None:
        ranked = EngineWorkCosts(CostsScript(COSTS)).ranked(works())
        self.assertEqual([LONG_TEXT_LAYER_BOOK, ARTICLE_FROM_PIXELS, UNOPENED, CLASSIFIED_LATER], names(ranked))

    def test_the_costs_are_asked_for_once(self) -> None:
        script = CostsScript(COSTS)
        costs = EngineWorkCosts(script)
        costs.by_key(costs.ranked(works()))
        self.assertEqual(1, len(script.asked))


class TestTheBatchListsTheCostOfEachWorkBoundForTheEngine(unittest.TestCase):
    def test_each_costed_work_is_listed_under_its_key(self) -> None:
        listed = EngineWorkCosts(CostsScript(COSTS)).by_key(works())
        self.assertEqual({"1": [20, 20], "4": [0, 900]}, listed)

    def test_a_failed_costing_halts_the_batch(self) -> None:
        line = StepGuard("drive-batch").outcome(lambda: EngineWorkCosts(CostsScript(None)).by_key(works()))
        self.assertEqual("halt", line["state"])


if __name__ == "__main__":
    unittest.main()
