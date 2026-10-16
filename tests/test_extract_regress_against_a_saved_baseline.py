from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _extract.paths import CorpusFile
from _extract.records import ExtractionRecord, ExtractionRecords
from _extract.regressbaseline import BaselineReference, BaselineSaving, baseline_path
from _extract.regression import STATE_CHANGED, STATE_NO_BASELINE, STATE_UNCHANGED, RegressionCheck
from _extract.regresssample import PER_PROPERTY, PER_WEIGHTED_PROPERTY, RANDOM_EXTRA, SampleSetChooser
from _extract.request import ExtractionRequest
from _vaults import TempVault, TextPdf

BASENAME = "Doe - 2020 - A Work"
ACCEPTED = "%% file p. 1 %%\n\nThe body as it was accepted."
REBUILT = "%% file p. 1 %%\n\nThe body as the code now builds it."
RESHAPED = "%% file p. 1 %%\n\nThe body as the code now\n\nbuilds it."


class Built:
    def __init__(self, text: str) -> None:
        self.text = text

    def rendered(self) -> "Built":
        return self


class BaselineCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("LIBRARY_DIR", "CORPUS_DIR").activate()
        self.addCleanup(self.vault.discard)
        self.pdf = TextPdf(self.vault.library / f"{BASENAME}.pdf").write()
        (self.vault.corpus / f"{BASENAME}.md").write_text("---\ntitle: A Work\n---\n", encoding="utf-8")
        self.note = CorpusFile(self.pdf)
        self.note.write(ACCEPTED, {})
        ExtractionRecords().write(BASENAME, ExtractionRecord(ExtractionRequest(()), reviewed="2026-10-01"))

    def checked(self, text: str, reference) -> dict:
        return RegressionCheck(lambda *_args: Built(text), 1, reference).checked(self.pdf)


class TestASavedBaseline(BaselineCase):
    def test_saving_keeps_the_rebuilt_body(self) -> None:
        self.checked(REBUILT, BaselineSaving())
        self.assertEqual(REBUILT + "\n", baseline_path(self.note).read_text(encoding="utf-8"))

    def test_saving_still_diffs_against_the_corpus_file(self) -> None:
        self.assertEqual(STATE_CHANGED, self.checked(REBUILT, BaselineSaving())["state"])

    def test_a_rebuild_matching_its_baseline_is_unchanged(self) -> None:
        self.checked(REBUILT, BaselineSaving())
        self.assertEqual(STATE_UNCHANGED, self.checked(REBUILT, BaselineReference())["state"])

    def test_a_rebuild_breaking_a_paragraph_changes_no_word(self) -> None:
        self.checked(REBUILT, BaselineSaving())
        compared = self.checked(RESHAPED, BaselineReference())
        self.assertEqual((STATE_CHANGED, 0), (compared["state"], compared["word_changes"]))

    def test_a_work_with_no_saved_baseline_is_named(self) -> None:
        self.assertEqual(STATE_NO_BASELINE, self.checked(REBUILT, BaselineReference())["state"])


class TestTheSampleSetChooser(unittest.TestCase):
    def test_each_property_takes_its_quota_and_ten_more_come_at_random(self) -> None:
        works = {f"Book {index}": {"book"} for index in range(10)}
        works.update({f"Noted {index}": {"footnotes"} for index in range(10)})
        works.update({f"Plain {index}": set() for index in range(20)})
        by_property, chosen = SampleSetChooser(works, set()).chosen()
        self.assertEqual((PER_PROPERTY, PER_WEIGHTED_PROPERTY), (len(by_property["book"]), len(by_property["footnotes"])))
        self.assertEqual(PER_PROPERTY + PER_WEIGHTED_PROPERTY + RANDOM_EXTRA, len(chosen))

    def test_cached_works_are_taken_first(self) -> None:
        works = {f"Book {index}": {"book"} for index in range(10)}
        cached = {"Book 7", "Book 8", "Book 9"}
        self.assertEqual(cached, set(SampleSetChooser(works, cached).chosen()[0]["book"]))

    def test_the_same_seed_chooses_the_same_works(self) -> None:
        works = {f"Work {index}": {"book"} for index in range(40)}
        self.assertEqual(SampleSetChooser(works, set(), 3).chosen(), SampleSetChooser(works, set(), 3).chosen())


if __name__ == "__main__":
    unittest.main()
