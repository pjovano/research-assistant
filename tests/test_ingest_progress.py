from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import vault
from _drive.script import ScriptRun, SkillScript
from _ingest.batch import BatchListing
from _ingest.progress import BatchPlaces, BatchProgress, MachineHealth, UpdateInterval, WorkStage
from _ingest.runlock import RunHolder, RunLock
from _drive.work import Halt
from _ingest.selection import BatchRecord, BatchRequest, BatchSelection, keys_by_stage
from _vault.scratch import RUN_LOCK_NAME
from _vaults import TempVault, TextPdf

FRESH_PDF = "fresh.pdf"
ROUTED_PDF = "routed.pdf"
FILED_PDF = "scan.pdf"
VOLUME_PDF = "volume.pdf"
FILED = "Doe - 2020 - A Work"
PLACED = "Poe - 2018 - A Third Work"
UNEXTRACTED = "Roe - 2019 - Another Work"
PDF_LINK = "[x.pdf](zotero://open-pdf/library/items/ABCD)\n\n"
BODY = PDF_LINK + "# One\n\nText.\n"
STARTED_AT = 1_790_000_000.0
HEALTH = {"samples": 60, "system": {"worst_thermal": "nominal"}, "alerts": [],
          "processes": [{"label": f"p{number}"} for number in range(8)]}


class HealthScript(SkillScript):
    def __init__(self, run: ScriptRun) -> None:
        super().__init__(Path("health.py"))
        self._run = run
        self.calls: list[tuple[str, ...]] = []

    def run(self, *args: str) -> ScriptRun:
        self.calls.append(args)
        return self._run


class ProgressCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("INBOX_DIR", "CORPUS_DIR", "VOLUMES_DIR").activate()
        self.addCleanup(self.vault.discard)
        self.works_dir = vault.SCRATCH_DIR / "ingest"
        self.backfill_works = vault.SCRATCH_DIR / "backfill" / "works"
        self.health = HealthScript(ScriptRun(0, json.dumps(HEALTH)))

    def state(self, name: str, state: dict) -> None:
        (self.works_dir / name).mkdir(parents=True, exist_ok=True)
        (self.works_dir / name / "state.json").write_text(json.dumps(state), encoding="utf-8")

    def note(self, basename: str, meta: dict, body: str) -> None:
        vault.write_frontmatter(vault.CORPUS_DIR / f"{basename}.md", meta, body)

    def progress(self, works: list[dict], machine: dict | None = None, lock_holder: int | None = None) -> dict:
        lock = RunLock(vault.SCRATCH_DIR / RUN_LOCK_NAME)
        lock.take(RunHolder(lock_holder or os.getpid(), "clean", STARTED_AT))
        BatchRecord(self.works_dir).write(RunHolder(os.getpid(), "clean", STARTED_AT), works)
        places = BatchPlaces(vault.INBOX_DIR, vault.VOLUMES_DIR, vault.SCRATCH_DIR)
        health = MachineHealth(self.health, UpdateInterval(machine or {}))
        progress = BatchProgress(BatchRecord(self.works_dir).read_if_held(lock), WorkStage(places), health)
        return progress.report(STARTED_AT + 90 * 60)


class TestOnlyTheRunHoldingTheLock(ProgressCase):
    def test_a_record_of_the_run_holding_the_lock_is_reported(self) -> None:
        self.assertEqual("progress", self.progress([])["state"])

    def test_a_record_of_a_run_another_process_displaced_is_not_reported(self) -> None:
        self.assertEqual("no-batch", self.progress([], lock_holder=os.getppid())["state"])


class TestTheWorksByStage(ProgressCase):
    def setUp(self) -> None:
        super().setUp()
        TextPdf(self.vault.inbox / FRESH_PDF).write()
        TextPdf(self.vault.inbox / ROUTED_PDF).write()
        self.state("routed", {"routed": True})
        TextPdf(vault.VOLUMES_DIR / VOLUME_PDF).write()
        self.note(FILED, {"source_type": ""}, PDF_LINK)
        self.state(FILED, {"routed": True, "inbox_pdf": FILED_PDF})
        self.note(PLACED, {"source_type": "monograph", "field": ["[[Logic]]"]}, BODY)
        self.note(UNEXTRACTED, {"source_type": ""}, PDF_LINK)
        works = [{"pdf": name, "from": "clean"} for name in (FRESH_PDF, ROUTED_PDF, FILED_PDF, VOLUME_PDF)]
        works += [{"basename": name, "from": "extract"} for name in (PLACED, UNEXTRACTED)]
        self.report = self.progress(works)

    def test_each_work_is_listed_at_the_stage_it_reached(self) -> None:
        self.assertEqual({"clean": [FRESH_PDF], "file": [ROUTED_PDF], "extract": [FILED_PDF, UNEXTRACTED],
                          "moved among the volumes": [VOLUME_PDF], "placed": [PLACED]}, self.report["stages"])

    def test_counts_the_works_and_the_works_done(self) -> None:
        self.assertEqual((6, 1), (self.report["works"], self.report["done"]))

    def test_states_the_time_elapsed(self) -> None:
        self.assertEqual(90, self.report["elapsed_minutes"])


class TestTheMachinesHealth(ProgressCase):
    def test_covers_the_update_interval(self) -> None:
        self.progress([], {"batch_update_minutes": 90})
        self.assertEqual([("report", "--hours", "1.5")], self.health.calls)

    def test_carries_the_five_fastest_growing_processes(self) -> None:
        self.assertEqual(5, len(self.progress([])["health"]["processes"]))

    def test_a_failed_report_is_named_and_the_progress_still_given(self) -> None:
        self.health = HealthScript(ScriptRun(1, "", "no journals"))
        report = self.progress([])
        self.assertEqual(("progress", True), (report["state"], "failed" in report["health"]["error"]))


class TestTheInterval(ProgressCase):
    def test_is_half_an_hour_by_default(self) -> None:
        self.assertEqual(30, self.progress([])["interval_minutes"])

    def test_with_no_batch_recorded_names_only_the_interval(self) -> None:
        places = BatchPlaces(vault.INBOX_DIR, vault.VOLUMES_DIR, vault.SCRATCH_DIR)
        report = BatchProgress(None, WorkStage(places), MachineHealth(self.health, UpdateInterval({}))).report(0.0)
        self.assertEqual({"state": "no-batch", "interval_minutes": 30}, report)


class TestTheSelection(ProgressCase):
    def selection(self) -> BatchSelection:
        queue = vault.SCRATCH_DIR / "backfill" / "queue.txt"
        queue.parent.mkdir(parents=True, exist_ok=True)
        queue.write_text(f"{PLACED}.pdf\n{UNEXTRACTED}.pdf\n{FILED}.pdf\n", encoding="utf-8")
        return BatchSelection(BatchListing(vault.INBOX_DIR, self.works_dir), queue)

    def test_a_backfill_keys_its_queue_lines_by_their_line_number(self) -> None:
        self.assertEqual([{"key": 2, "basename": UNEXTRACTED, "from": "extract"}, {"key": 3, "basename": FILED, "from": "extract"}],
                         self.selection().works(BatchRequest("extract", [], 2, 3)))

    def test_a_batch_keys_its_listing_in_order(self) -> None:
        for pdf in (FRESH_PDF, ROUTED_PDF):
            TextPdf(self.vault.inbox / pdf).write()
        self.state("routed", {"routed": "book"})
        self.assertEqual([{"key": 1, "pdf": FRESH_PDF, "from": "clean"}, {"key": 2, "pdf": ROUTED_PDF, "from": "file"}],
                         self.selection().works(BatchRequest("clean")))

    def test_chosen_keys_carry_their_works_in_the_order_given(self) -> None:
        self.assertEqual([FILED, UNEXTRACTED], [work["basename"] for work in
                                         self.selection().works(BatchRequest("extract", [3, 2]))])

    def test_a_key_outside_the_listing_halts(self) -> None:
        with self.assertRaises(Halt):
            self.selection().works(BatchRequest("extract", [4]))

    def test_a_batch_range_with_only_an_end_starts_at_the_first_work(self) -> None:
        for pdf in (FRESH_PDF, ROUTED_PDF):
            TextPdf(self.vault.inbox / pdf).write()
        self.assertEqual([1], [work["key"] for work in self.selection().works(BatchRequest("clean", [], None, 1))])

    def test_the_keys_are_grouped_by_stage(self) -> None:
        works = self.selection().works(BatchRequest("extract"))
        self.assertEqual({"extract": [1, 2, 3]}, keys_by_stage(works))


if __name__ == "__main__":
    unittest.main()
