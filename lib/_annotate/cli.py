from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pymupdf

import vault

from .markers import AKADEMIE_PREFIX, EditionAnchorIndex, EditionMarker
from .reader import AnnotationInventory, AnnotationRevision
from .spans import WordGrid
from .specs import AnnotationSpec, RevisionSpec
from .writer import AnnotationPlan, AnnotationWriter

CONTEXT_WORDS = 60
ANNOTATION_AUTHOR_KEY = "annotation_author"
EDITION_REFERENCE_RE = re.compile(r"^(?P<edition>[A-Z]+|[a-z]+)\s?(?P<number>\d+)$")


class AnchorReport:
    def __init__(self, path: Path) -> None:
        self._index = EditionAnchorIndex(path)

    def rendered(self) -> str:
        lines = [f"strategies: {', '.join(self._index.strategies())}"]
        lines.append(f"inline markers: {self._coverage()}")
        lines.append(f"marginal numbers: {'yes' if self._index.marginal.is_available else 'no'}")
        return "\n".join(lines)

    def _coverage(self) -> str:
        counts = self._index.inline.coverage()
        if not counts:
            return "none"
        total = sum(counts.values())
        detail = ", ".join(f"{form}={count}" for form, count in sorted(counts.items()))
        return f"{total} ({detail})"


class ReferenceLookup:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._index = EditionAnchorIndex(path)

    def rendered(self, reference: str) -> str:
        edition, number = self._parsed(reference)
        hits = self._index.inline.resolve(edition, number)
        if hits:
            return self._hits(hits)
        return self._bracketed(edition, number)

    def _parsed(self, reference: str) -> tuple[str, int]:
        text = reference.strip()
        if ":" in text:
            return self._parsed_akademie(text, reference)
        edition_reference = EDITION_REFERENCE_RE.match(text)
        if edition_reference is None:
            raise ValueError(
                f"reference must be an edition siglum and a page, as A137 or C12, or a volume and a page, "
                f"as 4:255, got {reference!r}")
        return edition_reference.group("edition").upper(), int(edition_reference.group("number"))

    def _parsed_akademie(self, text: str, reference: str) -> tuple[str, int]:
        volume, _, page = text.partition(":")
        if not volume.isdigit() or not page.isdigit():
            raise ValueError(f"Akademie reference must look like 4:255, got {reference!r}")
        return f"{AKADEMIE_PREFIX}{volume}", int(page)

    def _hits(self, hits) -> str:
        with pymupdf.open(self._path) as document:
            return "\n".join(self._hit_line(document, h) for h in hits)

    def _hit_line(self, document, marker) -> str:
        grid = WordGrid(document[marker.page - 1])
        text = grid.text(marker.word_index, marker.word_index + CONTEXT_WORDS)
        return (f"{marker.label} -> p{marker.page} "
                f"word {marker.word_index}\n    {text}")

    def _bracketed(self, edition: str, number: int) -> str:
        below, above = self._index.inline.bracketing(edition, number)
        return (f"{self._label(edition, number)}: no marker.\n"
                f"    nearest below: {self._describe(below)}\n"
                f"    nearest above: {self._describe(above)}\n"
                f"    read between them to place the passage.")

    def _label(self, edition: str, number: int) -> str:
        return EditionMarker.labelled(edition, number)

    def _describe(self, marker) -> str:
        if marker is None:
            return "none"
        return f"{marker.label} at p{marker.page} word {marker.word_index}"


class AnnotateCli:
    def __init__(self) -> None:
        self._parser = self._build_parser()

    def run(self, argv: list[str]) -> int:
        arguments = self._parser.parse_args(argv)
        try:
            return self._dispatch(arguments)
        except (FileNotFoundError, ValueError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 1

    def _dispatch(self, arguments) -> int:
        path = vault.LibraryPdf(arguments.pdf).path()
        handler = getattr(self, f"_run_{arguments.command}")
        return handler(path, arguments)

    def _run_anchors(self, path: Path, _arguments) -> int:
        print(AnchorReport(path).rendered())
        return 0

    def _run_locate(self, path: Path, arguments) -> int:
        print(ReferenceLookup(path).rendered(arguments.ref))
        return 0

    def _run_list(self, path: Path, arguments) -> int:
        print(AnnotationInventory(path).rendered(arguments.tag or ""))
        return 0

    def _run_plan(self, path: Path, arguments) -> int:
        requests = AnnotationSpec.loaded(Path(arguments.spec)).requests()
        print(AnnotationPlan(path).decisions(requests).rendered())
        return 0

    def _run_apply(self, path: Path, arguments) -> int:
        if not arguments.apply:
            self._run_plan(path, arguments)
            return self._dry_run_notice()
        requests = AnnotationSpec.loaded(Path(arguments.spec)).requests()
        writer = AnnotationWriter(path, self._author())
        writer.apply(requests)
        print(writer.report.rendered())
        return 0

    def _run_revise(self, path: Path, arguments) -> int:
        changes = RevisionSpec.loaded(Path(arguments.spec)).changes()
        revision = AnnotationRevision(path)
        if not arguments.apply:
            print(self._outcomes(revision.plan(changes)))
            return self._dry_run_notice()
        revision.apply(changes)
        print(self._outcomes(revision.outcomes))
        return 0

    def _outcomes(self, outcomes) -> str:
        lines = [outcome.rendered() for outcome in outcomes]
        return "\n".join(lines) if lines else "no changes"

    def _dry_run_notice(self) -> int:
        print("\n(dry run — nothing written; pass --apply to write)")
        return 0

    def _author(self) -> str | None:
        return vault.MACHINE.get(ANNOTATION_AUTHOR_KEY)

    def _build_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog="annotate.py")
        subparsers = parser.add_subparsers(dest="command", required=True)
        self._pdf_subparser(subparsers, "anchors")
        self._pdf_subparser(subparsers, "locate").add_argument("--ref", required=True)
        self._pdf_subparser(subparsers, "list").add_argument("--tag", default="")
        self._add_spec(subparsers, "plan")
        self._add_writable_spec(subparsers, "apply")
        self._add_writable_spec(subparsers, "revise")
        return parser

    def _pdf_subparser(self, subparsers, name: str) -> argparse.ArgumentParser:
        sub = subparsers.add_parser(name)
        sub.add_argument("pdf")
        return sub

    def _add_spec(self, subparsers, name: str) -> argparse.ArgumentParser:
        sub = self._pdf_subparser(subparsers, name)
        sub.add_argument("--spec", required=True)
        return sub

    def _add_writable_spec(self, subparsers, name: str) -> None:
        self._add_spec(subparsers, name).add_argument("--apply", action="store_true")
