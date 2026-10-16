from __future__ import annotations

import argparse
import os
from pathlib import Path

import vault

from _drive.runlock import RunLock
from _drive.steps import JsonLine, StepGuard
from _drive.work import Halt
from _extract.enginecost import CheapestFirst
from _vault.scratch import BACKFILL_ENTRY
from _extract.backfillcleanup import CleanupRouting
from _extract.backfillprep import PIXEL_PAGES_STATE, Preparation
from _extract.backfillrunner import ExtractScript
from _extract.backfillstep import DetachedStep, StepHost, StepLauncher
from _extract.backfilltrial import TrialRun
from _extract.backfillwork import BackfillQueue
from _extract.console import EXIT_OK
from _extract.paths import LibraryPdfs

BACKFILL_DIR = vault.SCRATCH_DIR / BACKFILL_ENTRY
PREP_RECORDS = {
    "pixels_only": Preparation.record_pixels_only,
    "one_chapter": Preparation.record_one_chapter,
    "fonts_checked": Preparation.record_fonts_checked,
}


class BackfillCommands:
    def __init__(self, directory: Path = BACKFILL_DIR, script: ExtractScript | None = None,
                 host: StepHost | None = None, order: CheapestFirst | None = None,
                 run_lock: RunLock | None = None) -> None:
        self._queue = BackfillQueue(directory)
        self._order = order or CheapestFirst.for_backfill(directory)
        self._run_lock = run_lock or RunLock.ingest()
        self._script = script or ExtractScript()
        self._host = host or StepHost(StepLauncher())
        self._engine_steps = {
            "prep": lambda work: Preparation(work, self._script).run(),
            "trial": lambda work: TrialRun(work, self._script).trial(),
            "retrial": lambda work: TrialRun(work, self._script).retrial(),
        }

    def queue(self, _args: argparse.Namespace) -> int:
        return JsonLine.emit(StepGuard("drive-queue").outcome(self._write_queue))

    def prep(self, args: argparse.Namespace) -> int:
        self._outcome_for_work(args, lambda work: Preparation(work, self._script).record_cleanup(args.cleanup))
        for option, record in PREP_RECORDS.items():
            if getattr(args, option):
                self._outcome_for_work(args, lambda work: record(Preparation(work, self._script)))
        self._record_pixel_pages(args)
        return JsonLine.emit(self._start(args, "prep"))

    def cleanup(self, args: argparse.Namespace) -> int:
        return JsonLine.emit(self._outcome_for_work(args, lambda work: CleanupRouting(work, self._script).route()))

    def trial(self, args: argparse.Namespace) -> int:
        return JsonLine.emit(self._start(args, "trial"))

    def retrial(self, args: argparse.Namespace) -> int:
        return JsonLine.emit(self._start(args, "retrial"))

    def run(self, args: argparse.Namespace) -> int:
        step_args = argparse.Namespace(command=f"drive-{args.step}", index=args.index)
        outcome = self._outcome_for_work(step_args, self._engine_steps[args.step])
        self._detached(args).record(outcome)
        return EXIT_OK

    def wait(self, args: argparse.Namespace) -> int:
        return JsonLine.emit(StepGuard(args.command).outcome(lambda: self._detached(args).wait()))

    def fonts_checked(self, args: argparse.Namespace) -> int:
        if args.pixels_only:
            self._outcome_for_work(args, lambda work: Preparation(work, self._script).record_pixels_only())
        recorded = self._record_pixel_pages(args)
        if recorded and recorded.get("state") != PIXEL_PAGES_STATE:
            return JsonLine.emit(recorded)
        return JsonLine.emit(self._outcome_for_work(args, self._record_fonts_checked))

    def _record_pixel_pages(self, args: argparse.Namespace) -> dict | None:
        if args.pixel_pages is None:
            return None
        return self._outcome_for_work(args, lambda work: Preparation(work, self._script).record_pixel_pages(
            args.pixel_pages))

    def _record_fonts_checked(self, work) -> dict:
        return Preparation(work, self._script).record_fonts_checked()

    def _start(self, args: argparse.Namespace, step: str) -> dict:
        return StepGuard(args.command).outcome(lambda: self._started_and_awaited(args, step))

    def _started_and_awaited(self, args: argparse.Namespace, step: str) -> dict:
        detached = self._detached(args)
        detached.start(step, args.index)
        return detached.wait()

    def _detached(self, args: argparse.Namespace) -> DetachedStep:
        return DetachedStep(self._queue.work(args.index), self._host)

    def _write_queue(self) -> dict:
        holder = self._run_lock.held_by_another(os.getpid())
        if holder is not None:
            raise Halt(f"a run holds the run lock, and a rewritten queue changes every work key: {holder.describe()}")
        pdfs = self._order.ordered([pdf.name for pdf in LibraryPdfs().without_body()])
        self._queue.write(pdfs)
        return {"state": "queued", "count": len(pdfs), "queue": str(self._queue.path)}

    def _outcome_for_work(self, args: argparse.Namespace, step) -> dict:
        return StepGuard(args.command).on_work(lambda: self._queue.work(args.index), step)
