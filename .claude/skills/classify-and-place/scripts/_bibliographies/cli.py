from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import vault

from _drive.steps import JsonLine

from .diagnostics import ReportBuilder
from .drive import ClassifyDriver
from .gloss_cli import GlossCommands
from .reshape_cli import ReshapeCommands
from .notes import Bibliographies, BibliographyNotFound, Corpus, NoteChange, NoteNotFound, Writing
from .opening import Opening
from .placement import RepeatedWorkList, WorkPlacement

EXIT_BLOCKING = 1
EXIT_UNRESOLVED = 2
EXIT_ALREADY_CLASSIFIED = 3
EXIT_REPEATED_WORK_LIST = 4


class ChangeSet:
    def __init__(self, label: str, changes: list[NoteChange]) -> None:
        self._label = label
        self._changes = changes

    def announce_applied(self) -> None:
        self._announce("changed")

    def announce_planned(self) -> None:
        self._announce("would change")

    def _announce(self, verb: str) -> None:
        names = [change.name for change in self._changes]
        print(f"{self._label}: {len(names)} {verb} -> {names}")

    def report(self, applied: bool) -> dict:
        return {self._label: [change.name for change in self._changes], "applied": applied}

    def write_all(self) -> None:
        for change in self._changes:
            change.write()


class CommandLine:
    def __init__(self) -> None:
        self._parser = argparse.ArgumentParser()
        self._add_commands()

    def run(self) -> None:
        args = self._parser.parse_args()
        try:
            args.handler(args)
        except (NoteNotFound, BibliographyNotFound) as unresolved:
            print(unresolved, file=sys.stderr)
            sys.exit(EXIT_UNRESOLVED)
        except RepeatedWorkList as repeated:
            print(repeated, file=sys.stderr)
            sys.exit(EXIT_REPEATED_WORK_LIST)

    def _add_commands(self) -> None:
        sub = self._parser.add_subparsers(dest="command", required=True)
        self._add_place(sub)
        self._add_check(sub)
        self._add_opening(sub)
        self._add_tree(sub)
        self._add_drive_classify(sub)
        GlossCommands().add_to(sub)
        ReshapeCommands().add_to(sub)

    def _add_place(self, sub) -> None:
        place = sub.add_parser("place", help="add one work to each bibliography its corpus file's field: names")
        place.add_argument("basename")
        place.add_argument("--apply", action="store_true",
                           help="write the changes; without it, report and write nothing")
        place.add_argument("--json", action="store_true", help="print one JSON object instead of the summary line")
        place.set_defaults(handler=self._place)

    def _add_tree(self, sub) -> None:
        tree = sub.add_parser("tree", help="read-only: every bibliography's name, folder, author, aliases, and the "
                                           "bibliographies its ## Maps lists")
        tree.set_defaults(handler=self._tree)

    def _add_drive_classify(self, sub) -> None:
        drive = sub.add_parser("drive-classify", help="ingest: write the work classifier's answers into the corpus "
                                                      "file and place it; one JSON line")
        drive.add_argument("basename")
        drive.add_argument("--answers", default=None, type=Path,
                           help="the work classifier's answers file; without it, discard the work's answers file "
                                "and print its path for the worker")
        drive.set_defaults(handler=self._drive_classify)

    def _add_check(self, sub) -> None:
        check = sub.add_parser("check", help="read-only diagnostics; exits non-zero on a blocking group")
        check.add_argument("--json", action="store_true", help="print the groups as one JSON object")
        check.set_defaults(handler=self._check)

    def _add_opening(self, sub) -> None:
        opening = sub.add_parser("opening",
                                 help="read-only: a corpus file's classification, headings, and prefatory text")
        opening.add_argument("basename")
        opening.add_argument("--reclassify", action="store_true",
                             help="report an already classified corpus file without the refusal exit code")
        opening.set_defaults(handler=self._opening)

    @staticmethod
    def _place(args: argparse.Namespace) -> None:
        note = Corpus().note(args.basename)
        changes = WorkPlacement(note, Bibliographies()).plan()
        change_set = ChangeSet("bibliographies", changes)
        if args.apply:
            vault.ensure_dirs()
            change_set.write_all()
        CommandLine._announce(change_set, args)

    @staticmethod
    def _announce(change_set: ChangeSet, args: argparse.Namespace) -> None:
        if args.json:
            print(json.dumps(change_set.report(args.apply), ensure_ascii=False))
        elif args.apply:
            change_set.announce_applied()
        else:
            change_set.announce_planned()

    @staticmethod
    def _tree(_args: argparse.Namespace) -> None:
        print(json.dumps([entry.summary() for entry in Bibliographies().entries()], indent=2, ensure_ascii=False))

    @staticmethod
    def _drive_classify(args: argparse.Namespace) -> None:
        driver = ClassifyDriver()
        if args.answers is None:
            JsonLine.emit(driver.prepare(args.basename))
        else:
            JsonLine.emit(driver.classify(args.basename, args.answers))

    @staticmethod
    def _opening(args: argparse.Namespace) -> None:
        Corpus().note(args.basename)
        opening = Opening(args.basename)
        print(json.dumps(opening.report(), indent=2, ensure_ascii=False))
        if opening.classification.is_written and not args.reclassify:
            sys.exit(EXIT_ALREADY_CLASSIFIED)

    @staticmethod
    def _check(args: argparse.Namespace) -> None:
        report = ReportBuilder(Bibliographies(), Corpus(), Writing()).build()
        if args.json:
            print(json.dumps(report.as_dict(), ensure_ascii=False))
        else:
            report.print()
        if not report.is_clean:
            sys.exit(EXIT_BLOCKING)


def main() -> None:
    CommandLine().run()
