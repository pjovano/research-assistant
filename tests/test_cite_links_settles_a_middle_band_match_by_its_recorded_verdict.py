from __future__ import annotations

import json
import os
import time
import unittest

from _support import LiveTree

LiveTree.activate()

from cite import (
    CONFIRM,
    REJECT,
    STATUS_NOT_OFFERED,
    STATUS_PLANNED,
    STATUS_RECORDED,
    CitationVerdicts,
    NoteLinks,
    RebuildFactory,
    RunGate,
    RunLockHeld,
    ScoreBand,
    Settlement,
    Verdict,
    VerdictsFile,
    VerdictsFileCorrupt,
)
from test_cite_links import (
    BROKEN_ENTRY,
    CITING,
    CITING_FRONTMATTER,
    EARLIER,
    ENTRY,
    KANT,
    REVIEW_ENTRY,
    SCORED_BODY,
    FakeParser,
    LibraryTestCase,
    linked,
)

from _drive.runlock import RunHolder, RunLock
from references import CitationScoring, HeldWorks

MIDDLE_BAND_SCORE = 89.0
STRAY_ENTRY = "Doe, Jane. An Unrelated Monograph. 1994."


class VerdictTestCase(LibraryTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.write_note(CITING, CITING_FRONTMATTER, SCORED_BODY)
        self.verdicts = CitationVerdicts()

    def record(self, entry: str, work: str, verdict: str, citing: str = CITING) -> None:
        self.verdicts.record([Verdict(citing, entry, work, verdict)])

    def links(self) -> NoteLinks:
        return NoteLinks(CITING, CitationScoring(HeldWorks.from_library(), FakeParser()), CitationVerdicts())

    def offered(self) -> list[tuple[str, str]]:
        return [(item["entry"], item["basename"]) for item in self.links().status()["to_confirm"]]


class TestARecordedVerdictSettlesTheMatch(VerdictTestCase):
    def test_an_unsettled_middle_band_match_is_reported(self) -> None:
        self.assertEqual([(REVIEW_ENTRY, EARLIER)], self.offered())

    def test_a_confirmed_match_is_no_longer_reported(self) -> None:
        self.record(REVIEW_ENTRY, EARLIER, CONFIRM)
        self.assertEqual([], self.offered())

    def test_apply_links_a_confirmed_middle_band_match(self) -> None:
        self.record(REVIEW_ENTRY, EARLIER, CONFIRM)
        self.links().apply()
        self.assertIn(linked(REVIEW_ENTRY, EARLIER), self.note_text(CITING))

    def test_a_rejected_match_is_no_longer_reported(self) -> None:
        self.record(REVIEW_ENTRY, EARLIER, REJECT)
        self.assertEqual([], self.offered())

    def test_apply_never_links_a_rejected_match(self) -> None:
        self.record(REVIEW_ENTRY, EARLIER, REJECT)
        self.links().apply()
        self.assertIn(f"\n{REVIEW_ENTRY}\n", self.note_text(CITING))

    def test_apply_never_links_a_rejected_match_whose_score_is_automatic(self) -> None:
        self.record(BROKEN_ENTRY, EARLIER, REJECT)
        self.links().apply()
        self.assertIn(f"\n{BROKEN_ENTRY}\n", self.note_text(CITING))

    def test_a_verdict_on_another_work_leaves_the_match_reported(self) -> None:
        self.record(REVIEW_ENTRY, KANT, REJECT)
        self.assertEqual([(REVIEW_ENTRY, EARLIER)], self.offered())

    def test_a_verdict_from_another_citing_work_leaves_the_match_reported(self) -> None:
        self.record(REVIEW_ENTRY, EARLIER, REJECT, citing=KANT)
        self.assertEqual([(REVIEW_ENTRY, EARLIER)], self.offered())


class TestAConfirmedLinkIsNeverStale(VerdictTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.write_note(CITING, CITING_FRONTMATTER,
                        f"[x.pdf](zotero://open-pdf/x)\n\n# Bibliography\n\n{linked(STRAY_ENTRY, EARLIER)}\n")

    def stale(self) -> list[str]:
        return [item["entry"] for item in self.links().status()["stale"]]

    def test_an_unconfirmed_link_whose_entry_names_nothing_is_stale(self) -> None:
        self.assertEqual([STRAY_ENTRY], self.stale())

    def test_a_confirmed_link_whose_entry_names_nothing_is_not_stale(self) -> None:
        self.record(STRAY_ENTRY, EARLIER, CONFIRM)
        self.assertEqual([], self.stale())


class TestTheVerdictsRecord(VerdictTestCase):
    def test_a_second_record_keeps_the_first_verdict(self) -> None:
        self.record(REVIEW_ENTRY, EARLIER, CONFIRM)
        self.record(ENTRY, EARLIER, REJECT)
        stored = json.loads(self.verdicts.path.read_text(encoding="utf-8"))
        self.assertEqual({REVIEW_ENTRY: {EARLIER: CONFIRM}, ENTRY: {EARLIER: REJECT}}, stored[CITING])

    def test_the_record_lives_in_the_library(self) -> None:
        self.assertEqual(self.vault.library, self.verdicts.path.parent)

    def test_a_record_that_is_not_json_is_refused(self) -> None:
        self.verdicts.path.write_text("{", encoding="utf-8")
        with self.assertRaises(VerdictsFileCorrupt):
            CitationVerdicts().of(CITING)

    def test_a_verdict_outside_the_vocabulary_is_refused(self) -> None:
        with self.assertRaises(LookupError):
            Verdict(CITING, REVIEW_ENTRY, EARLIER, "maybe")


class SettlementTestCase(VerdictTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.lock = RunLock.ingest()

    def settlement(self, request) -> Settlement:
        return self.settlement_in_run(request, None)

    def settlement_in_run(self, request, run_session: int | None) -> Settlement:
        return Settlement(request, RebuildFactory(FakeParser(), CitationVerdicts()), RunGate(self.lock, run_session))

    def verdicts_file(self, *verdicts: Verdict):
        path = self.vault.named("verdicts.json")
        path.write_text(json.dumps([verdict.as_dict() for verdict in verdicts]), encoding="utf-8")
        return VerdictsFile(path)


class TestSettlingAScoreBand(SettlementTestCase):
    def test_the_read_only_form_plans_every_match_in_the_band(self) -> None:
        report = self.settlement(ScoreBand(MIDDLE_BAND_SCORE, 90.0, CONFIRM)).plan()
        self.assertEqual([(REVIEW_ENTRY, EARLIER, MIDDLE_BAND_SCORE, STATUS_PLANNED)],
                         [(row["entry"], row["work"], row["score"], row["status"]) for row in report["verdicts"]])

    def test_the_band_excludes_its_upper_bound(self) -> None:
        self.assertEqual([], self.settlement(ScoreBand(80.0, MIDDLE_BAND_SCORE, CONFIRM)).plan()["verdicts"])

    def test_the_read_only_form_records_nothing_and_writes_nothing(self) -> None:
        before = self.note_text(CITING)
        self.settlement(ScoreBand(70.0, 90.0, CONFIRM)).plan()
        self.assertEqual((before, False), (self.note_text(CITING), self.verdicts.path.exists()))

    def test_the_writing_form_records_and_links_a_confirmed_band(self) -> None:
        report = self.settlement(ScoreBand(70.0, 90.0, CONFIRM)).apply()
        self.assertEqual(STATUS_RECORDED, report["verdicts"][0]["status"])
        self.assertIn(linked(REVIEW_ENTRY, EARLIER), self.note_text(CITING))

    def test_the_writing_form_records_a_rejected_band_without_linking(self) -> None:
        self.settlement(ScoreBand(70.0, 90.0, REJECT)).apply()
        self.assertEqual(([], f"\n{REVIEW_ENTRY}\n" in self.note_text(CITING)), (self.offered(), True))


class TestSettlingAVerdictsFile(SettlementTestCase):
    def test_a_pair_the_middle_band_does_not_offer_is_never_recorded(self) -> None:
        report = self.settlement(self.verdicts_file(Verdict(CITING, ENTRY, KANT, CONFIRM))).apply()
        self.assertEqual((STATUS_NOT_OFFERED, False),
                         (report["verdicts"][0]["status"], self.verdicts.path.exists()))

    def test_a_recorded_reject_may_be_revised_to_confirm(self) -> None:
        self.record(REVIEW_ENTRY, EARLIER, REJECT)
        self.settlement(self.verdicts_file(Verdict(CITING, REVIEW_ENTRY, EARLIER, CONFIRM))).apply()
        self.assertIn(linked(REVIEW_ENTRY, EARLIER), self.note_text(CITING))


class TestSettlingWaitsForTheRunLock(SettlementTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.lock.take(RunHolder(os.getpid(), "test", time.time()))

    def test_the_writing_form_is_refused_while_a_run_holds_the_lock(self) -> None:
        with self.assertRaises(RunLockHeld):
            self.settlement(ScoreBand(70.0, 90.0, CONFIRM)).apply()

    def test_a_refused_writing_form_records_nothing_and_writes_nothing(self) -> None:
        before = self.note_text(CITING)
        with self.assertRaises(RunLockHeld):
            self.settlement(ScoreBand(70.0, 90.0, CONFIRM)).apply()
        self.assertEqual((before, False), (self.note_text(CITING), self.verdicts.path.exists()))

    def test_the_read_only_form_runs_while_a_run_holds_the_lock(self) -> None:
        self.assertEqual(1, self.settlement(ScoreBand(70.0, 90.0, CONFIRM)).plan()[STATUS_PLANNED])

    def test_the_run_holding_the_lock_records_its_own_verdicts(self) -> None:
        self.settlement_in_run(ScoreBand(70.0, 90.0, CONFIRM), os.getpid()).apply()
        self.assertIn(linked(REVIEW_ENTRY, EARLIER), self.note_text(CITING))

    def test_another_run_holding_the_lock_refuses_the_writing_form(self) -> None:
        with self.assertRaises(RunLockHeld):
            self.settlement_in_run(ScoreBand(70.0, 90.0, CONFIRM), os.getpid() + 1).apply()


if __name__ == "__main__":
    unittest.main()
