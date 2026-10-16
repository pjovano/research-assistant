from __future__ import annotations

import argparse
import json
import sys

import pagetext
import vault

from .quotes import QuoteVerification
from .textlayer import TermLocation, TextLayerQuality

DEFAULT_LOCATE_LIMIT = 25
DEFAULT_QUALITY_SAMPLE_PAGES = 40
SUCCESS_EXIT_CODE = 0
NOT_VERIFIED_EXIT_CODE = 1
USAGE_EXIT_CODE = 2
POOR_TEXT_LAYER_EXIT_CODE = 3
FAILURE_EXIT_CODE = 4


def main() -> None:
    sys.exit(VerifyCli().run(sys.argv[1:]))


class VerifyCli:
    def __init__(self) -> None:
        self._parser = self._build_parser()

    def run(self, argv: list[str]) -> int:
        if not argv:
            self._parser.print_help()
            return USAGE_EXIT_CODE
        arguments = self._parser.parse_args(argv)
        try:
            return arguments.run(arguments)
        except (ValueError, FileNotFoundError) as error:
            print(error, file=sys.stderr)
            return FAILURE_EXIT_CODE

    def _run_verify(self, arguments) -> int:
        pdf = vault.LibraryPdf(arguments.pdf).path()
        verification = QuoteVerification(pdf, arguments.quote, arguments.threshold)
        self._emitter(arguments)(verification)
        return SUCCESS_EXIT_CODE if verification.verified() else NOT_VERIFIED_EXIT_CODE

    def _run_locate(self, arguments) -> int:
        pdf = vault.LibraryPdf(arguments.pdf).path()
        self._emitter(arguments)(TermLocation(pdf, arguments.term, arguments.max))
        return SUCCESS_EXIT_CODE

    def _run_quality(self, arguments) -> int:
        quality = TextLayerQuality(vault.LibraryPdf(arguments.pdf).path(), arguments.pages or None)
        self._emitter(arguments)(quality)
        return SUCCESS_EXIT_CODE if quality.is_good() else POOR_TEXT_LAYER_EXIT_CODE

    def _emitter(self, arguments):
        return self._emit_json if arguments.json else self._emit_text

    def _emit_json(self, result) -> None:
        print(json.dumps(result.payload(), indent=2, ensure_ascii=False))

    def _emit_text(self, result) -> None:
        print(result.rendered())

    def _build_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog="verify.py")
        subparsers = parser.add_subparsers(dest="command", required=True)
        self._add_verify(subparsers)
        self._add_locate(subparsers)
        self._add_quality(subparsers)
        return parser

    def _add_verify(self, subparsers) -> None:
        verify = self._pdf_subparser(subparsers, "verify", "is this quotation in this PDF, and on which printed folio")
        verify.add_argument("quote")
        verify.add_argument("--threshold", type=float, default=pagetext.DEFAULT_NEAR_MATCH_THRESHOLD)
        verify.set_defaults(run=self._run_verify)

    def _add_locate(self, subparsers) -> None:
        locate = self._pdf_subparser(subparsers, "locate", "which pages of this PDF mention a term")
        locate.add_argument("term")
        locate.add_argument("--max", type=int, default=DEFAULT_LOCATE_LIMIT)
        locate.set_defaults(run=self._run_locate)

    def _add_quality(self, subparsers) -> None:
        quality = self._pdf_subparser(subparsers, "quality",
                                      "is the text layer trustworthy, or must the pages be read visually")
        quality.add_argument("--pages", type=int, default=DEFAULT_QUALITY_SAMPLE_PAGES)
        quality.set_defaults(run=self._run_quality)

    def _pdf_subparser(self, subparsers, name: str, purpose: str) -> argparse.ArgumentParser:
        subparser = subparsers.add_parser(name, help=purpose)
        subparser.add_argument("pdf")
        subparser.add_argument("--json", action="store_true")
        return subparser
