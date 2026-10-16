from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from references import CitationGraph, CitationParserUnavailable

from _cite.rebuild import ConflictCopies, LinksRebuild
from _cite.settle import RunGate, ScoreBand, Settlement, VerdictsFile
from _cite.verdicts import VERDICTS

DESCRIPTION = "Stage 3: place a wikilink on every bibliography entry, or footnote, that names a held work."
Handler = Callable[[argparse.Namespace], dict | list[dict]]


@dataclass(frozen=True)
class CommandSpec:
    name: str
    help_text: str
    handler: Handler


class CommandLine:
    def run(self, argv: list[str]) -> None:
        parser = self._parser()
        args = parser.parse_args(argv or ["--help"])
        print(json.dumps(self._rows(args), indent=2, ensure_ascii=False))

    @staticmethod
    def _rows(args: argparse.Namespace) -> dict | list[dict]:
        try:
            return args.handler(args)
        except (CitationParserUnavailable, LookupError) as error:
            raise SystemExit(str(error)) from error

    def _parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog="cite.py", description=DESCRIPTION)
        commands = parser.add_subparsers(dest="command")
        self._add_rebuild(commands, CommandSpec("status", "report which corpus files would gain links (read-only)",
                                                self._status))
        self._add_rebuild(commands, CommandSpec("apply", "write the links into every corpus file that gains one",
                                                self._apply))
        self._add_settle(commands)
        self._add_graph(commands, CommandSpec("cites", "the held works this corpus file's entries and footnotes "
                                                       "link to", self._cites))
        self._add_graph(commands, CommandSpec("cited-by", "the corpus files whose entries or footnotes link to this "
                                                          "work", self._cited_by))
        return parser

    def _add_rebuild(self, commands, spec: CommandSpec) -> None:
        command = commands.add_parser(spec.name, help=spec.help_text)
        command.add_argument("basenames", nargs="*", help="corpus files to consider; none means every corpus file")
        command.add_argument("--cited", metavar="BASENAME",
                             help="consider instead every corpus file whose text names an author of this held work")
        command.set_defaults(handler=spec.handler)

    @staticmethod
    def _rebuild(args: argparse.Namespace) -> LinksRebuild:
        if args.cited and args.basenames:
            raise LookupError("name corpus files or pass --cited, not both")
        return LinksRebuild.citing(args.cited) if args.cited else LinksRebuild(args.basenames)

    def _add_settle(self, commands) -> None:
        command = commands.add_parser("settle", help="record the verdicts on middle-band matches")
        command.add_argument("basenames", nargs="*",
                             help="with --scores, the corpus files to consider; none means every corpus file")
        request = command.add_mutually_exclusive_group(required=True)
        request.add_argument("--verdicts", type=Path, metavar="FILE",
                             help="a JSON list of verdicts, each with citing, entry, work, and verdict")
        request.add_argument("--scores", nargs=2, type=float, metavar=("LOW", "HIGH"),
                             help="every middle-band match scored from LOW up to, not including, HIGH")
        command.add_argument("--verdict", choices=VERDICTS, help="with --scores, the verdict on every match")
        command.add_argument("--apply", action="store_true",
                             help="record the verdicts and link the confirmed matches; without it, write nothing")
        command.add_argument("--in-run", type=int, metavar="PID",
                             help="with --apply, the session process whose ingest run holds the run lock: the "
                                  "run records its own verdicts")
        command.set_defaults(handler=self._settle)

    def _add_graph(self, commands, spec: CommandSpec) -> None:
        command = commands.add_parser(spec.name, help=spec.help_text)
        command.add_argument("basename", help="a held work's basename")
        command.set_defaults(handler=spec.handler)

    @classmethod
    def _status(cls, args: argparse.Namespace) -> dict:
        return {"conflict_copies": ConflictCopies().names(), "rows": cls._rebuild(args).status()}

    @classmethod
    def _apply(cls, args: argparse.Namespace) -> list[dict]:
        return cls._rebuild(args).apply()

    @classmethod
    def _settle(cls, args: argparse.Namespace) -> dict:
        settlement = Settlement(cls._settle_request(args), gate=RunGate(run_session=args.in_run))
        return settlement.apply() if args.apply else settlement.plan()

    @staticmethod
    def _settle_request(args: argparse.Namespace) -> VerdictsFile | ScoreBand:
        if args.verdicts:
            if args.basenames or args.verdict:
                raise LookupError("--verdicts names its own corpus files and verdicts; pass neither beside it")
            return VerdictsFile(args.verdicts)
        if args.verdict is None:
            raise LookupError("--scores needs --verdict confirm or --verdict reject")
        return ScoreBand(*args.scores, args.verdict, tuple(args.basenames))

    @staticmethod
    def _cites(args: argparse.Namespace) -> dict:
        return CitationGraph().cites(args.basename)

    @staticmethod
    def _cited_by(args: argparse.Namespace) -> dict:
        return CitationGraph().cited_by(args.basename)
