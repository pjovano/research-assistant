from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _extract.backfillscope import excluded_spans
from _extract.backfillverify import TrialVerification

SHARED_PAGE = 40
OUTLINE = [{"title": "1 Opening", "file_page": 1, "level": 1},
           {"title": "2 Argument", "file_page": 12, "level": 1},
           {"title": "Acknowledgements", "file_page": SHARED_PAGE, "level": 1},
           {"title": "Bibliography", "file_page": SHARED_PAGE, "level": 1}]
SCOPE = ["--exclude", f"{SHARED_PAGE}: Acknowledgements", f"{SHARED_PAGE}: Bibliography"]


class TestOutlineEntriesInsideASpanExcludedWithinOnePage(unittest.TestCase):
    def missing(self, trial_text: str, scope: list[str]) -> list[dict]:
        trial = Path(self.enterContext(tempfile.TemporaryDirectory())) / "trial.md"
        trial.write_text(trial_text)
        return TrialVerification(OUTLINE, excluded_spans(scope)).missing_headings({"written": str(trial)})

    def test_the_entry_the_span_opens_on_is_not_required(self) -> None:
        self.assertEqual([], self.missing("# 1 Opening\n# 2 Argument\n# Bibliography\n", SCOPE))

    def test_the_entry_the_span_resumes_at_is_still_required(self) -> None:
        missing = self.missing("# 1 Opening\n# 2 Argument\n", SCOPE)
        self.assertEqual([{"title": "Bibliography", "file_page": SHARED_PAGE}], missing)

    def test_a_point_naming_no_entry_still_resumes_at_the_top_of_its_page(self) -> None:
        scope = ["--exclude", "12", f"{SHARED_PAGE}: Received"]
        missing = self.missing("# 1 Opening\n", scope)
        self.assertEqual(["Acknowledgements", "Bibliography"], [heading["title"] for heading in missing])

    def test_an_opening_that_names_another_entry_does_not_exclude_this_one(self) -> None:
        scope = ["--exclude", f"{SHARED_PAGE}: Bibliography", "end"]
        missing = self.missing("# 1 Opening\n# 2 Argument\n", scope)
        self.assertEqual([{"title": "Acknowledgements", "file_page": SHARED_PAGE}], missing)


if __name__ == "__main__":
    unittest.main()
