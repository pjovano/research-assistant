from __future__ import annotations

import argparse
import json
from pathlib import Path

from _extract.console import EXIT_OK, JsonOutput
from _extract.correctionlisting import CorrectionListing
from _extract.correctionrun import MalformedCorrections
from _extract.correctionstore import TrialCorrections, WorkContext
from _extract.failures import UsageFailure
from _extract.paths import CorpusFile, PdfLocator
from _extract.records import CORRECTIONS_KEY, MODE_KEY, REVIEWED_KEY, ExtractionRecord, ExtractionRecords
from _extract.request import ExtractionRequest
from _extract.trial import TrialNote


class CorrectionCommands:
    def correct(self, args: argparse.Namespace) -> int:
        pdf_path, note = PdfLocator().with_note(args.pdf)
        target = correction_target(note, args.body)
        result = WorkContext(pdf_path).corrected(target.body(), CorrectionsFile(Path(args.corrections)).load())
        written = args.apply and bool(result.applied)
        if written:
            target.write(result.text.rendered(), result.applied, args.replace)
        JsonOutput().emit({"written": str(target.path) if written else None, "counts": result.counts(),
                           "outcomes": result.outcomes})
        return EXIT_OK

    def correction_listing(self, args: argparse.Namespace) -> int:
        pdf_path, note = PdfLocator().with_note(args.pdf)
        JsonOutput().emit(CorrectionListing(pdf_path, correction_target(note, args.body)).as_dict())
        return EXIT_OK


class CorrectionsFile:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> object:
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as failure:
            raise MalformedCorrections(f"cannot read the corrections file {self._path}: {failure}") from failure


class TrialTarget:
    def __init__(self, note: CorpusFile) -> None:
        self._note = note
        self._trial = TrialNote(note).require()

    @property
    def basename(self) -> str:
        return self._note.basename

    @property
    def path(self) -> Path:
        return self._trial.path

    def body(self) -> str:
        return self._trial.body()

    def report(self) -> dict:
        return self._trial.report()

    def excluded(self) -> tuple[tuple[str, str], ...]:
        return ExtractionRequest.from_record(self._trial.frontmatter(), self._note.basename).excluded

    def write(self, text: str, applied: list[dict], _replace: bool) -> None:
        self._trial.write_body(text)
        store = TrialCorrections(self._note)
        store.save(store.load() + applied)


class ReviewedBodyTarget:
    def __init__(self, note: CorpusFile) -> None:
        self._note = note
        self._entry = ExtractionRecords().entry(note.basename) or {}
        if not (note.has_body() and self._entry.get(REVIEWED_KEY)):
            raise UsageFailure(f"{note.basename} is no reviewed work: --body corrects only a reviewed work's body")

    @property
    def basename(self) -> str:
        return self._note.basename

    @property
    def path(self) -> Path:
        return self._note.path

    def body(self) -> str:
        return self._note.body()

    def report(self) -> dict:
        return {}

    def excluded(self) -> tuple[tuple[str, str], ...]:
        return ExtractionRequest.from_stored(self._entry, self._note.basename).excluded

    def write(self, text: str, applied: list[dict], replace: bool) -> None:
        if not replace:
            raise UsageFailure(f"{self._note.basename} has a body: pass --replace to write the corrected body")
        self._note.write(text, {})
        corrections = tuple(self._entry.get(CORRECTIONS_KEY) or []) + tuple(applied)
        request = ExtractionRequest.from_stored(self._entry, self._note.basename)
        record = ExtractionRecord(request, self._entry.get(MODE_KEY), self._entry.get(REVIEWED_KEY), corrections)
        ExtractionRecords().write(self._note.basename, record)


def correction_target(note: CorpusFile, body: bool) -> TrialTarget | ReviewedBodyTarget:
    return ReviewedBodyTarget(note) if body else TrialTarget(note)
