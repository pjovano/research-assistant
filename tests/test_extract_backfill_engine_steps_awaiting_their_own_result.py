from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from test_extract_backfill_driver import BackfillCase, probed


class TestAnEngineStepAwaitingItsOwnResult(unittest.TestCase):
    def test_one_call_returns_the_finished_steps_state(self) -> None:
        case = BackfillCase(self, probed())
        self.assertEqual("fonts", case.invoke("prep")["state"])

    def test_one_call_leaves_no_running_step_behind(self) -> None:
        case = BackfillCase(self, probed())
        case.invoke("prep")
        self.assertFalse((case.work_dir / "step.pid").exists())


class TestPreparingAWorkWhoseFontsAreChecked(unittest.TestCase):
    def test_the_fonts_checked_flag_lets_one_call_convert(self) -> None:
        case = BackfillCase(self, probed())
        self.assertEqual("ready", case.invoke("prep", fonts_checked=True)["state"])

    def test_the_fonts_checked_flag_records_the_check(self) -> None:
        case = BackfillCase(self, probed())
        case.invoke("prep", fonts_checked=True)
        self.assertTrue(case.read("state.json")["fonts_checked"])


if __name__ == "__main__":
    unittest.main()
