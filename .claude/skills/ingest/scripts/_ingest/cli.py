from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import vault
from surya_servers import RUN_PATH
from synced_folder import ConfiguredSyncedFolder

from _drive.detached import StepHost
from _drive.script import REPOSITORY_ROOT
from _drive.steps import EXIT_OK, JsonLine, StepGuard
from _drive.work import QUEUE_NAME, WORKS_NAME, IngestWorks, ListedWorks
from _vault.scratch import BACKFILL_ENTRY, INGEST_ENTRY
from _writing.reading_list import ProjectReadingLists

from _ingest.batch import BatchListing
from _ingest.checkout import Checkout, CheckoutReadiness, WorkingDirectoryReadiness
from _ingest.citations import JUDGE_ENTRY, JudgedMatches, JudgeListings, SettleStep, VerdictsRecorder
from _ingest.cite import CiteDriver, GraphRun
from _ingest.glosses import GlossDriver
from _ingest.readings import PlacedWorks, ReadingsStep
from _ingest.reshape import ReshapeDriver
from _ingest.exclusive import DetachedStepsReadiness, EngineRunReadiness, RunLockReadiness
from _ingest.runlock import RunEnd, RunHolder, RunLock, RunTeardown, SessionProcess
from _ingest.detach import DetachedCommand, DetachedSteps, IngestLauncher
from _ingest.prefetchstep import PREFETCH_KEY, DetachedPrefetch
from _ingest.progress import BatchPlaces, BatchProgress, MachineHealth, UpdateInterval, WorkStage
from _ingest.preflight import (
    PROBE_CITEKEY,
    START_CLEAN,
    START_EXTRACT,
    EngineReadiness,
    InstalledEngine,
    Preflight,
    SyncedFolderReadiness,
    VisionReadiness,
    ZoteroReadiness,
)
from _ingest.scripts import SiblingScripts
from _ingest.selection import BatchRecord, BatchRequest, BatchSelection, EngineWorkCosts, keys_by_stage, work_pdf
from _ingest.tail import CheckStep, CiteStep, IndexStep


class Commands:
    def preflight(self, args: argparse.Namespace) -> int:
        return self._emit("preflight", lambda: Preflight(self._checks(args.start)).outcome())

    def synced_folder(self, args: argparse.Namespace) -> int:
        return self._emit("synced-folder", lambda: Preflight([self._synced_folder_check(args.start)]).outcome())

    def _checks(self, start: str) -> list:
        machine = [*self._exclusive_checks(), CheckoutReadiness(Checkout(REPOSITORY_ROOT)),
                   WorkingDirectoryReadiness(Path.cwd()), EngineReadiness(InstalledEngine.models),
                   self._synced_folder_check(start)]
        if start == START_EXTRACT:
            return machine
        return [*machine, ZoteroReadiness(SiblingScripts.file(), BetterBibtexProbe.run), VisionReadiness()]

    @staticmethod
    def _synced_folder_check(start: str) -> SyncedFolderReadiness:
        return SyncedFolderReadiness.for_start(start, ConfiguredSyncedFolder.of_machine().built)

    @staticmethod
    def _exclusive_checks() -> list:
        detached_parents = [vault.SCRATCH_DIR / INGEST_ENTRY, vault.SCRATCH_DIR / BACKFILL_ENTRY / WORKS_NAME]
        return [RunLockReadiness(Commands._run_lock(), SessionProcess.pid()), EngineRunReadiness(RUN_PATH),
                DetachedStepsReadiness(detached_parents)]

    def drive_batch(self, args: argparse.Namespace) -> int:
        return self._emit("drive-batch", lambda: self._recorded_batch(args))

    def _recorded_batch(self, args: argparse.Namespace) -> dict:
        holder = RunHolder(SessionProcess.pid(), args.origin, time.time())
        self._run_lock().take(holder)
        costs = EngineWorkCosts(SiblingScripts.extract())
        works = self._selection(costs).works(BatchRequest(args.origin, args.works, args.first, args.last))
        BatchRecord(self._works_dir()).write(holder, works)
        listed = ListedWorks(self._works_dir())
        for work in works:
            listed.list(work["key"], work_pdf(work))
        return {"state": "batch", "count": len(works), "by_key": str(listed.by_key), "stages": keys_by_stage(works),
                "costs": costs.by_key(works)}

    def list_works(self, args: argparse.Namespace) -> int:
        works = self._selection(EngineWorkCosts(SiblingScripts.extract())).works(BatchRequest(args.origin))
        print(json.dumps({"state": "listed", "works": works}, ensure_ascii=False))
        return EXIT_OK

    def _selection(self, costs: EngineWorkCosts) -> BatchSelection:
        return BatchSelection(BatchListing(vault.INBOX_DIR, self._works_dir()),
                              vault.SCRATCH_DIR / BACKFILL_ENTRY / QUEUE_NAME, costs)

    @staticmethod
    def _works_dir() -> Path:
        return vault.SCRATCH_DIR / INGEST_ENTRY

    def drive_release(self, _args: argparse.Namespace) -> int:
        teardown = RunTeardown(SiblingScripts.extract(), vault.ScratchSweeps.reviewed(),
                               DetachedPrefetch(self._works_dir() / PREFETCH_KEY))
        run_end = RunEnd(self._run_lock(), SessionProcess.pid(), teardown)
        return self._emit("drive-release", run_end.finish)

    def progress(self, _args: argparse.Namespace) -> int:
        places = BatchPlaces(vault.INBOX_DIR, vault.VOLUMES_DIR, vault.SCRATCH_DIR)
        health = MachineHealth(SiblingScripts.health(), UpdateInterval(vault.MACHINE))
        record = BatchRecord(places.works_dir).read_if_held(self._run_lock())
        progress = BatchProgress(record, WorkStage(places), health)
        return self._emit("progress", lambda: progress.report(time.time()))

    @staticmethod
    def _run_lock() -> RunLock:
        return RunLock.ingest()

    def drive_check(self, _args: argparse.Namespace) -> int:
        return self._emit("drive-check", CheckStep(SiblingScripts.bibliographies()).run)

    def drive_cite(self, args: argparse.Namespace) -> int:
        if args.key is None:
            listings = JudgeListings(self._works_dir() / JUDGE_ENTRY)
            return self._emit("drive-cite", CiteStep(SiblingScripts.cite(), listings, SiblingScripts.graph()).run)
        driver = CiteDriver(SiblingScripts.cite(), SiblingScripts.graph(), self._works_dir())
        return JsonLine.emit(driver.link(args.key))

    def drive_settle(self, _args: argparse.Namespace) -> int:
        judged = JudgedMatches(self._works_dir() / JUDGE_ENTRY)
        recorder = VerdictsRecorder(SiblingScripts.cite(), SessionProcess.pid())
        return self._emit("drive-settle", SettleStep(judged, recorder, GraphRun(SiblingScripts.graph())).run)

    def drive_index(self, _args: argparse.Namespace) -> int:
        return self._emit("drive-index", IndexStep(SiblingScripts.search()).run)

    def drive_gloss_plan(self, args: argparse.Namespace) -> int:
        return JsonLine.emit(self._glosses().plan(args.keys, args.everything))

    def drive_gloss_finish(self, args: argparse.Namespace) -> int:
        return JsonLine.emit(self._glosses().finish(args.directory))

    def _glosses(self) -> GlossDriver:
        return GlossDriver(SiblingScripts.bibliographies(), self._works_dir())

    def drive_clusters(self, _args: argparse.Namespace) -> int:
        return JsonLine.emit(ReshapeDriver(SiblingScripts.bibliographies(), self._works_dir()).clusters())

    def drive_merge(self, _args: argparse.Namespace) -> int:
        return JsonLine.emit(ReshapeDriver(SiblingScripts.bibliographies(), self._works_dir()).merge())

    def drive_reshape(self, args: argparse.Namespace) -> int:
        return JsonLine.emit(ReshapeDriver(SiblingScripts.bibliographies(), self._works_dir()).reshape(args.answers))

    def drive_readings(self, _args: argparse.Namespace) -> int:
        lists = ProjectReadingLists(vault.BIBLIOGRAPHIES_DIR / vault.READING_LISTS_FOLDER)
        return self._emit("drive-readings", ReadingsStep(lists, PlacedWorks(vault.list_held_notes())).run)

    def drive_detach(self, args: argparse.Namespace) -> int:
        return self._emit("drive-detach", lambda: self._detached().start(args.key, DetachedCommand(args.step_command)))

    def drive_run(self, args: argparse.Namespace) -> int:
        self._detached().run(args.key, DetachedCommand(args.step_command))
        return EXIT_OK

    def drive_wait(self, args: argparse.Namespace) -> int:
        return self._emit("drive-wait", lambda: self._detached().wait(args.key))

    @staticmethod
    def _detached() -> DetachedSteps:
        return DetachedSteps(IngestWorks(vault.SCRATCH_DIR / INGEST_ENTRY), StepHost(IngestLauncher()))

    @staticmethod
    def _emit(command: str, step) -> int:
        return JsonLine.emit(StepGuard(command).outcome(step))


class BetterBibtexProbe:
    @staticmethod
    def run() -> None:
        import zotero
        zotero.get_item_key(PROBE_CITEKEY)


DRIVE_STEPS = {
    "drive-check": "the batch's tail: bibliographies.py check, its blocking groups and author proposals as questions",
    "drive-settle": "the batch's tail: the citation judge's verdicts recorded by cite.py settle --apply, then "
                    "graph.py sync on the files linked",
    "drive-readings": "the batch's tail: each wanted entry of a project reading list that names a placed work, "
                      "moved under Held",
    "drive-index": "the batch's tail: Stage 6, search.py sync, then status, with the skill's one retry",
    "drive-release": "the run's last step: stop the run's prefetch, then extract.py stop-servers, then release the "
                     "run lock; none of them if another session holds the lock",
}


DETACHED_STEPS = {
    "drive-detach": "start the command after -- in the background, beside the key's batch work directory; running",
    "drive-run": "run the command after -- and record its last JSON line; started by drive-detach, never directly",
    "drive-wait": "wait up to eight minutes for the key's detached command; its JSON line, or running",
}


class CommandLine:
    def parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog="ingest.py", description="The ingest workflow's batch-wide steps.")
        subparsers = parser.add_subparsers(dest="command", required=True)
        preflight = subparsers.add_parser("preflight", help="check the machine before a batch's first PDF; one JSON "
                                                            "line, ready or halt")
        synced = subparsers.add_parser("synced-folder", help="read-only: preflight's synced-folder check alone, the "
                                                             "conflict copies and the files whose bytes are not on "
                                                             "disk; one JSON line, ready or halt")
        for starting in (preflight, synced):
            starting.add_argument("--from", dest="start", choices=(START_CLEAN, START_EXTRACT), default=START_CLEAN,
                                  help="the stage the batch starts from (default clean)")
        for name, does in DRIVE_STEPS.items():
            subparsers.add_parser(name, help=f"{does}; one JSON line")
        self._add_drive_cite(subparsers)
        self._add_drive_gloss(subparsers)
        self._add_drive_reshape(subparsers)
        self._add_drive_batch(subparsers)
        self._add_list_works(subparsers)
        self._add_detached(subparsers)
        subparsers.add_parser("progress", help="read-only: the recorded batch's works by stage, and the machine's "
                                               "health over the update interval; one JSON line")
        return parser

    @staticmethod
    def _add_drive_cite(subparsers) -> None:
        cite = subparsers.add_parser("drive-cite", help="Stage 3 for one work: cite.py apply on the work, then on "
                                                        "every corpus file naming one of its authors, then graph.py "
                                                        "sync on the files written; without a key, the batch's tail: "
                                                        "cite.py status, apply, then graph.py sync; one JSON line")
        cite.add_argument("key", nargs="?", default=None, help="the work key; none means the batch's tail")

    @staticmethod
    def _add_drive_gloss(subparsers) -> None:
        plan = subparsers.add_parser("drive-gloss-plan", help="Stage 5: copy each work's description onto its "
                                                              "listings, then the bibliographies to introduce, each "
                                                              "with the bibliography introducer's listing under "
                                                              "ingest/glosses/; one JSON line")
        plan.add_argument("keys", nargs="*", help="the work keys of the works placed in this batch")
        plan.add_argument("--all", dest="everything", action="store_true",
                          help="every bibliography listing a work or a map")
        finish = subparsers.add_parser("drive-gloss-finish", help="Stage 5: write the bibliography introducer's "
                                                                  "answers into the bibliography; one JSON line")
        finish.add_argument("directory", help="the bibliography's directory under ingest/glosses/")

    @staticmethod
    def _add_drive_reshape(subparsers) -> None:
        subparsers.add_parser("drive-clusters", help="the reshaping's listing: the citation graph's clusters and "
                                                     "findings, the uncovered authors, and the batch's nominations, "
                                                     "for the bibliography shaper, cut into parts; shape, or "
                                                     "nothing; one JSON line")
        subparsers.add_parser("drive-merge", help="merge the answers files the bibliography shaper wrote for the "
                                                  "parts of the listing into one; merged, or aside; one JSON line")
        reshape = subparsers.add_parser("drive-reshape", help="carry out the bibliography shaper's answers: create "
                                                              "each bibliography named and move each work named; "
                                                              "one JSON line")
        reshape.add_argument("answers", help="the shaper's answers file")

    @staticmethod
    def _add_drive_batch(subparsers) -> None:
        batch = subparsers.add_parser("drive-batch", help="list the batch under work keys, link each key to its batch "
                                                          "work directory, and record the run for `progress`; one "
                                                          "JSON line")
        CommandLine._add_origin(batch)
        batch.add_argument("--start", dest="first", type=int, default=None, help="the first work's key, from 1")
        batch.add_argument("--end", dest="last", type=int, default=None, help="the last work's key")
        batch.add_argument("--works", nargs="+", type=int, default=[], metavar="KEY",
                           help="carry the works under these keys of `list-works` instead")

    @staticmethod
    def _add_list_works(subparsers) -> None:
        listing = subparsers.add_parser("list-works", help="read-only: the works a batch would carry, each with its "
                                                           "key; one JSON line")
        CommandLine._add_origin(listing)

    @staticmethod
    def _add_origin(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--from", dest="origin", choices=(START_CLEAN, START_EXTRACT), default=START_CLEAN,
                            help="clean: each inbox PDF, each filed work of an earlier batch with a stage left, "
                                 "and each corpus file with a body and no classification; "
                                 "extract: the backfill queue's lines")


    @staticmethod
    def _add_detached(subparsers) -> None:
        for name, does in DETACHED_STEPS.items():
            step = subparsers.add_parser(name, help=f"{does}; one JSON line")
            step.add_argument("key", help="the work key the step is for, or tail for the batch's tail")
            if name != "drive-wait":
                step.add_argument("step_command", nargs=argparse.REMAINDER, help="-- and the command to run")


def main(argv: list[str] | None = None) -> int:
    args = CommandLine().parser().parse_args(argv)
    return getattr(Commands(), args.command.replace("-", "_"))(args)
