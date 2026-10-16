from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from references import CitationParser, HeldWorks

from _discover.cited import ANY_CITING_WORK, UnheldWorks
from _discover.merging import MergeReport

DESCRIPTION = "Discover: the unheld works the held works cite, and the merged reading-list candidates. Read-only."


class CommandLine:
    def run(self, argv: list[str]) -> None:
        parser = self._parser()
        if not argv:
            parser.print_help()
            return
        args = parser.parse_args(argv)
        print(json.dumps(args.handler(args), indent=2, ensure_ascii=False))

    def _parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog="discover.py", description=DESCRIPTION)
        commands = parser.add_subparsers(dest="command")
        unheld = commands.add_parser(
            "unheld", help="the bibliography and footnote entries of held works that name no held work")
        unheld.add_argument("basenames", nargs="+", help="held works to read")
        unheld.add_argument("--min-citing", type=int, default=ANY_CITING_WORK,
                            help="keep only the entries cited by at least this many of the named works")
        unheld.set_defaults(handler=self._unheld)
        merge = commands.add_parser(
            "merge", help="deduplicate, mark held, count local citations, and order the scouts' candidates from stdin")
        merge.add_argument("--unheld", type=Path, help="the JSON an `unheld` run printed")
        merge.add_argument("--known", type=Path, help="the known items: `unheld` entries, as {\"entries\": [...]}")
        merge.set_defaults(handler=self._merge)
        return parser

    @staticmethod
    def _unheld(args: argparse.Namespace) -> dict:
        return UnheldWorks(HeldWorks.from_library(), CitationParser()).over(args.basenames, args.min_citing)

    @classmethod
    def _merge(cls, args: argparse.Namespace) -> dict:
        report = MergeReport(HeldWorks.from_library(), cls._json_at(args.unheld), cls._json_at(args.known))
        return report.over(cls._as_reports(json.load(sys.stdin)))

    @staticmethod
    def _json_at(path: Path | None) -> dict:
        return json.loads(path.read_text(encoding="utf-8")) if path else {}

    @staticmethod
    def _as_reports(loaded) -> list[dict]:
        return loaded if isinstance(loaded, list) else [loaded]
