from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .glossing import Descriptions, GlossCopy, GlossPlan
from .introducing import IntroductionListing, IntroductionWrite
from .notes import Bibliographies, Corpus
from .placement import WorkOrder

EXIT_PROBLEMS = 1


class JsonOutput:
    @staticmethod
    def emit(payload: dict, out: Path | None) -> None:
        text = json.dumps(payload, indent=2, ensure_ascii=False)
        if out is None:
            print(text)
            return
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")


class GlossCommands:
    def add_to(self, sub) -> None:
        self._add_copy(sub)
        self._add_plan(sub)
        self._add_listing(sub)
        self._add_write(sub)

    def _add_copy(self, sub) -> None:
        copy = sub.add_parser("gloss-copy", help="give each listing of every bibliography its work's description as "
                                                 "its gloss; without --apply, report and write nothing")
        copy.add_argument("--apply", action="store_true", help="write the changes")
        copy.set_defaults(handler=self._copy)

    def _add_plan(self, sub) -> None:
        plan = sub.add_parser("gloss-plan", help="read-only: the bibliographies to introduce: those the named works "
                                                 "sit on, those named, and each without an introduction; or every "
                                                 "bibliography with --all")
        plan.add_argument("--works", nargs="*", default=[], metavar="BASENAME", help="the works newly placed")
        plan.add_argument("--bibliographies", nargs="*", default=[], metavar="NAME",
                          help="bibliographies the reshaping touched, planned beside those the works sit on")
        plan.add_argument("--all", action="store_true", help="every bibliography listing a work or a map")
        plan.set_defaults(handler=self._plan)

    def _add_listing(self, sub) -> None:
        listing = sub.add_parser("gloss-listing", help="read-only: the bibliography introducer's listing for one "
                                                       "bibliography: its introduction, its maps, its groups with "
                                                       "their notes, its works with their descriptions, and its "
                                                       "unsorted works")
        listing.add_argument("name", help="the bibliography")
        listing.add_argument("--out", type=Path, default=None, help="write the listing here instead of stdout")
        listing.set_defaults(handler=self._listing)

    def _add_write(self, sub) -> None:
        write = sub.add_parser("gloss-write", help="write the bibliography introducer's answers into a bibliography: "
                                                   "its introduction, its group notes, and the group of each "
                                                   "unsorted work; with --check, report and write nothing")
        write.add_argument("name", help="the bibliography")
        write.add_argument("--answers", type=Path, required=True, help="the bibliography introducer's answers file")
        write.add_argument("--check", action="store_true", help="report the problems and write nothing")
        write.set_defaults(handler=self._write)

    @staticmethod
    def _copy(args: argparse.Namespace) -> None:
        changes = GlossCopy(Bibliographies(), Descriptions(Corpus())).changes()
        if args.apply:
            for change in changes:
                change.write()
        JsonOutput.emit({"changed": [change.name for change in changes], "applied": args.apply}, None)

    @staticmethod
    def _plan(args: argparse.Namespace) -> None:
        plan = GlossPlan(Bibliographies(), Corpus())
        planned = plan.for_all() if args.all else plan.for_works(args.works, args.bibliographies)
        JsonOutput.emit({"bibliographies": planned}, None)

    @staticmethod
    def _listing(args: argparse.Namespace) -> None:
        JsonOutput.emit(IntroductionListing(Bibliographies(), Corpus()).of(args.name), args.out)

    @staticmethod
    def _write(args: argparse.Namespace) -> None:
        answers = json.loads(args.answers.read_text(encoding="utf-8"))
        write = IntroductionWrite(Bibliographies().named(args.name), answers, WorkOrder(Corpus()))
        problems = write.problems()
        written = not problems and not args.check
        if written:
            write.write()
        JsonOutput.emit({"bibliography": args.name, "written": written, "problems": problems}, None)
        if problems:
            sys.exit(EXIT_PROBLEMS)
