from __future__ import annotations

import argparse
import sys

import vault
from datetime import date
from pathlib import Path

from _extract.acceptance import Acceptance
from _extract.console import EXIT_CHANGED, EXIT_OK, JsonOutput
from _extract.paths import CorpusFile, LibraryPdfs, PdfLocator
from _extract.regression import STATE_CHANGED, CachedConversion, RegressionCheck, RegressionSample, ReviewedWorks
from _extract.regressbaseline import reference_for
from _extract.regresssample import SampleSet, SampleSetChooser, properties_of
from _extract.stage import EngineSession, StageCommands
from _extract.trial import TrialNote


class ReviewCommands:
    def accept(self, args: argparse.Namespace) -> int:
        _pdf_path, note = PdfLocator().with_note(args.pdf)
        acceptance = Acceptance(note, TrialNote(note), date.today().isoformat())
        written = acceptance.accept_replacing() if args.replace else acceptance.accept()
        JsonOutput().emit({"written": str(written), "reviewed": note.reviewed()})
        return EXIT_OK

    def regress(self, args: argparse.Namespace) -> int:
        sample, pdf_paths = self._regressed(args)
        with EngineSession():
            works = RegressionCheck(StageCommands().build, args.jobs, reference_for(args.baseline)).run(pdf_paths)
        JsonOutput().emit({"sample": sample, "works": works})
        return EXIT_CHANGED if any(work["state"] == STATE_CHANGED for work in works) else EXIT_OK

    def regress_sample(self, args: argparse.Namespace) -> int:
        reviewed = ReviewedWorks().all()
        properties = {vault.basename_of(pdf): properties_of(pdf) for pdf in reviewed}
        cached = {vault.basename_of(pdf) for pdf in reviewed if CachedConversion().holds(pdf)}
        by_property, works = SampleSetChooser(properties, cached, args.seed).chosen()
        sample_set = SampleSet()
        sample_set.save(by_property, works)
        JsonOutput().emit({"path": str(sample_set.path), "works": len(works),
                           "cached": sum(work in cached for work in works),
                           "by_property": {name: len(chosen) for name, chosen in by_property.items()}})
        return EXIT_OK

    @staticmethod
    def _regressed(args: argparse.Namespace) -> tuple[dict | None, list[Path]]:
        if args.pdf:
            return None, [PdfLocator().resolve(raw) for raw in args.pdf]
        if args.sample_set:
            basenames = SampleSet().basenames()
            return {"sample_set": len(basenames)}, [vault.LIBRARY_DIR / f"{name}.pdf" for name in basenames]
        reviewed = ReviewedWorks().all()
        sample = RegressionSample(reviewed, len(reviewed) if args.all else args.sample)
        chosen = sample.chosen()
        return sample.as_dict(chosen), chosen

    def review_status(self, _args: argparse.Namespace) -> int:
        pending = [pdf for pdf in LibraryPdfs().all() if self._awaits_review(pdf)]
        for pdf in pending:
            print(pdf.name)
        print(f"{len(pending)} library PDFs have a corpus file body not yet reviewed", file=sys.stderr)
        return EXIT_OK

    @staticmethod
    def _awaits_review(pdf_path: Path) -> bool:
        return CorpusFile(pdf_path).has_body() and not ReviewedWorks.marks(pdf_path)
