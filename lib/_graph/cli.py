from __future__ import annotations

import argparse
import json
from collections.abc import Callable

import rag
from references import CitationParser, CitationParserUnavailable, HeldWorks

from _graph.clusters import ClusterReport
from _graph.contexts import CitationContexts
from _graph.library import LibraryGraph
from _graph.neighbours import DEFAULT_NEIGHBOURS, Neighbourhood
from _graph.store import GraphStore
from _graph.sync import GraphSync
from _graph.vectors import StoredCentroids

DESCRIPTION = ("The citation graph: the works the corpus files cite, held and unheld, the neighbours each work has by "
               "citation and by embedding, the clusters they form, and the passages where one work speaks of another.")
Handler = Callable[[argparse.Namespace], dict]


class CommandLine:
    def run(self, argv: list[str]) -> None:
        parser = self._parser()
        args = parser.parse_args(argv or ["--help"])
        print(json.dumps(self._result(args), indent=2, ensure_ascii=False))

    @staticmethod
    def _result(args: argparse.Namespace) -> dict:
        try:
            return args.handler(args)
        except (CitationParserUnavailable, LookupError) as error:
            raise SystemExit(str(error)) from error

    def _parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog="graph.py", description=DESCRIPTION)
        commands = parser.add_subparsers(dest="command")
        self._add_sync(commands)
        self._add_neighbours(commands)
        commands.add_parser("clusters", help="the clusters the works form, and the findings they raise").set_defaults(
            handler=self._clusters)
        self._add_contexts(commands)
        return parser

    def _add_sync(self, commands) -> None:
        command = commands.add_parser("sync", help="bring the graph store up to date with the corpus files")
        command.add_argument("basenames", nargs="*", help="corpus files to sync; none means every corpus file")
        command.add_argument("--rebuild", action="store_true", help="discard the store and build it again")
        command.set_defaults(handler=self._sync)

    def _add_neighbours(self, commands) -> None:
        command = commands.add_parser("neighbours", help="the works nearest one work, with the signals behind each")
        command.add_argument("basename", help="a corpus file's basename")
        command.add_argument("--k", type=int, default=DEFAULT_NEIGHBOURS, help="how many neighbours to list")
        command.set_defaults(handler=self._neighbours)

    def _add_contexts(self, commands) -> None:
        command = commands.add_parser("contexts", help="the passages where the citing work speaks of the cited work")
        command.add_argument("citing", help="the citing work's basename")
        command.add_argument("cited", help="the cited work's basename")
        command.set_defaults(handler=self._contexts)

    @staticmethod
    def _sync(args: argparse.Namespace) -> dict:
        store = GraphStore()
        if args.rebuild:
            store.clear()
        sync = GraphSync(store, HeldWorks.from_library(), CitationParser(), StoredCentroids(rag.EmbeddingStore()))
        return sync.run(args.basenames or None)

    @staticmethod
    def _neighbours(args: argparse.Namespace) -> dict:
        return Neighbourhood(LibraryGraph.loaded(GraphStore()), args.k).of(args.basename)

    @staticmethod
    def _clusters(_args: argparse.Namespace) -> dict:
        return ClusterReport(LibraryGraph.loaded(GraphStore())).report()

    @staticmethod
    def _contexts(args: argparse.Namespace) -> dict:
        passages = CitationContexts.between(args.citing, args.cited).passages()
        return {"citing": args.citing, "cited": args.cited, "passages": passages}
