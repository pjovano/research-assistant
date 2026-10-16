from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from citation_graph import GraphStore

from .gloss_cli import JsonOutput
from .listingparts import ListingParts
from .notes import Bibliographies, Corpus
from .partsdir import PartAnswers, PartsDirectory
from .reshaping import Reshape, ReshapeAnswers, ReshapeRefused, ShapeListing

EXIT_REFUSED = 5


class ReshapeCommands:
    def add_to(self, sub) -> None:
        self._add_listing(sub)
        self._add_merge(sub)
        self._add_reshape(sub)

    def _add_listing(self, sub) -> None:
        listing = sub.add_parser("shape-listing", help="read-only: the bibliography shaper's listing: the tree, the "
                                                       "citation graph's clusters and findings, the authors of five or "
                                                       "more works without a bibliography, the batch's nominations, "
                                                       "and the works named by each, described")
        listing.add_argument("--nominations", type=Path, default=None,
                             help="the nominations file drive-classify wrote for the batch")
        listing.add_argument("--out", type=Path, default=None, help="write the listing here instead of stdout")
        listing.add_argument("--parts", type=Path, default=None,
                             help="cut the listing into parts under the size budget, <dir>/<n>/listing.json, and "
                                  "print their count instead of the listing")
        listing.set_defaults(handler=self._listing)

    def _add_merge(self, sub) -> None:
        merge = sub.add_parser("merge-answers", help="merge the answers files the bibliography shaper wrote for the "
                                                     "parts of a listing, <dir>/<n>/answers.json, into one answers "
                                                     "file: each repeated answer once, and no conflicting move or fold")
        merge.add_argument("--parts", type=Path, required=True, help="the directory shape-listing --parts wrote")
        merge.add_argument("--out", type=Path, required=True, help="write the merged answers file here")
        merge.set_defaults(handler=self._merge)

    def _add_reshape(self, sub) -> None:
        reshape = sub.add_parser("reshape", help="create the bibliographies the shaper's answers name, each under its "
                                                 "parent's ## Maps, and move each named work: its field:, its listings, "
                                                 "its placement")
        reshape.add_argument("--answers", type=Path, required=True, help="the bibliography shaper's answers file")
        reshape.add_argument("--apply", action="store_true", help="write; without it, check and report")
        reshape.set_defaults(handler=self._reshape)

    @staticmethod
    def _listing(args: argparse.Namespace) -> None:
        nominations = _nominations_at(args.nominations)
        listing = ShapeListing(Bibliographies(), Corpus(), GraphStore()).of(nominations)
        if args.parts is None:
            JsonOutput.emit(listing, args.out)
            return
        ReshapeCommands._emit_parts(listing, args)

    @staticmethod
    def _emit_parts(listing: dict, args: argparse.Namespace) -> None:
        if args.out is not None:
            JsonOutput.emit(listing, args.out)
        parts = ListingParts(listing).cut()
        PartsDirectory(args.parts).write(parts)
        JsonOutput.emit({"parts": len(parts)}, None)

    @staticmethod
    def _merge(args: argparse.Namespace) -> None:
        answers = PartAnswers(PartsDirectory(args.parts))
        JsonOutput.emit(answers.merged(), args.out)
        JsonOutput.emit(answers.report(), None)

    @staticmethod
    def _reshape(args: argparse.Namespace) -> None:
        reshape = Reshape(ReshapeAnswers.read(args.answers))
        try:
            report = reshape.apply() if args.apply else reshape.plan()
        except ReshapeRefused as refused:
            print(json.dumps({"refused": str(refused)}, ensure_ascii=False))
            sys.exit(EXIT_REFUSED)
        JsonOutput.emit(report, None)


def _nominations_at(path: Path | None) -> list[dict]:
    if path is None or not path.exists():
        return []
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return list(loaded.get("nominations", [])) if isinstance(loaded, dict) else list(loaded)
