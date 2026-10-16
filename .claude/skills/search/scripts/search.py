from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable


def _lib_dir() -> Path:
    here = Path(__file__).resolve()
    return next(parent / "lib" for parent in here.parents if (parent / "lib" / "vault.py").is_file())


sys.path.insert(0, str(_lib_dir()))
import rag
import vault
from rag import ERROR_KEY

FAILURE_EXIT_CODE = 1
USAGE_EXIT_CODE = 2

Command = Callable[[argparse.Namespace], int]


class SearchCli:
    def __init__(self) -> None:
        self._parser = self._build_parser()

    def run(self, argv: list[str]) -> int:
        if not argv:
            self._parser.print_help()
            return USAGE_EXIT_CODE
        arguments = self._parser.parse_args(argv)
        try:
            return arguments.run(arguments)
        except (rag.EmbeddingUnavailable, rag.EmbeddingModelMismatch, rag.TokenizerUnavailable) as error:
            self._print({ERROR_KEY: str(error)})
            return FAILURE_EXIT_CODE

    def _run_status(self, _arguments: argparse.Namespace) -> int:
        report = rag.IndexStatus().report()
        self._print(report)
        return 0 if report["consistent"] else FAILURE_EXIT_CODE

    def _run_sync(self, arguments: argparse.Namespace) -> int:
        vault.ensure_dirs()
        sync = rag.StoreSync()
        if arguments.rebuild:
            sync.rebuild()
        else:
            sync.run()
        report = sync.report()
        self._print(report)
        return FAILURE_EXIT_CODE if report["unreadable"] else 0

    def _run_query(self, arguments: argparse.Namespace) -> int:
        reranker = None if arguments.no_rerank else rag.LlamaReranker()
        search = rag.HybridSearch(rag.SearchIndex.on_this_machine(), reranker)
        self._print(search.results(arguments.text, arguments.k))
        return 0

    def _run_chunks(self, arguments: argparse.Namespace) -> int:
        self._print(rag.FullTextStore().stored_of(arguments.basename))
        return 0

    def _run_outline(self, arguments: argparse.Namespace) -> int:
        report = rag.CorpusOutline().of(arguments.basename)
        self._print(report)
        return FAILURE_EXIT_CODE if ERROR_KEY in report else 0

    def _run_check_embeddings(self, _arguments: argparse.Namespace) -> int:
        report = rag.EmbeddingCheck(rag.OllamaEmbedder()).report()
        self._print(report)
        return 0 if report["passes"] else FAILURE_EXIT_CODE

    def _print(self, payload: object) -> None:
        print(json.dumps(payload, indent=2, ensure_ascii=False))

    def _build_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog="search.py")
        subparsers = parser.add_subparsers(dest="command", required=True)
        subparsers.add_parser("status").set_defaults(run=self._run_status)
        self._add_sync(subparsers)
        self._add_query(subparsers)
        self._add_basename_command(subparsers, "chunks", self._run_chunks)
        self._add_basename_command(subparsers, "outline", self._run_outline)
        subparsers.add_parser("check-embeddings").set_defaults(run=self._run_check_embeddings)
        return parser

    def _add_sync(self, subparsers: argparse._SubParsersAction) -> None:
        sync = subparsers.add_parser("sync")
        sync.add_argument("--rebuild", action="store_true")
        sync.set_defaults(run=self._run_sync)

    def _add_query(self, subparsers: argparse._SubParsersAction) -> None:
        query = subparsers.add_parser("query")
        query.add_argument("text", nargs="+")
        query.add_argument("--k", type=int, default=rag.DEFAULT_RESULTS)
        query.add_argument("--no-rerank", action="store_true")
        query.set_defaults(run=self._run_query)

    @staticmethod
    def _add_basename_command(subparsers: argparse._SubParsersAction, name: str, run: Command) -> None:
        command = subparsers.add_parser(name)
        command.add_argument("basename")
        command.set_defaults(run=run)


def main() -> None:
    sys.exit(SearchCli().run(sys.argv[1:]))


if __name__ == "__main__":
    main()
