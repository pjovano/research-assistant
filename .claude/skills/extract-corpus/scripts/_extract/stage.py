from __future__ import annotations

import argparse
import contextlib
import sys
from pathlib import Path

from engine_slots import SlotsAgreement
from surya_servers import EngineRun, ReaperProcess

from _extract.build import BuildInputs, ConversionOptions, ConversionPlan, CorpusBuild, DoubtfulPagesRemain
from _extract.console import EXIT_DOUBTFUL, EXIT_OK, JsonOutput
from _extract.layer import TextLayer
from _extract.layersample import LayerSample, LayerSampleReport, SampleUnit
from _extract.notationpages import NotationPagePlan
from _extract.pagelabels import PageLabelWriter
from _extract.paths import CorpusFile, PdfLocator
from _extract.ranges import PageRanges
from _extract.readings import WorkerReadings
from _extract.scanlayer import LayerCoverage
from _extract.records import ExtractionRecord, ExtractionRecords
from _extract.report import DoubtfulReport, ExtractReport, ProbeReport, WrittenBody
from _extract.request import CLEARED_RECORD_FIELDS, EXTRACTION_MODE_FIELD, ExtractionRequest
from _extract.scope import GivenScope, ScopeListing
from _extract.trial import TrialNote


class EngineSession:
    def __init__(self, run: EngineRun | None = None) -> None:
        self._run = run or EngineRun(servers_agreement=SlotsAgreement.on_this_machine())

    def __enter__(self) -> EngineSession:
        self._run.started()
        ReaperProcess().ensure_running(self._reaper_command())
        return self

    def __exit__(self, *_exception) -> None:
        self._run.finished()

    @staticmethod
    def _reaper_command() -> list[str]:
        return [sys.executable, str(Path(__file__).resolve().parents[1] / "extract.py"), "reap-servers"]


class ConversionSession:
    def __init__(self, plan: ConversionPlan, page_count: int) -> None:
        self._session = contextlib.nullcontext() if plan.is_cached(page_count) else EngineSession()

    def __enter__(self) -> ConversionSession:
        self._session.__enter__()
        return self

    def __exit__(self, *exception) -> None:
        self._session.__exit__(*exception)


class BodyTarget:
    def __init__(self, note: CorpusFile, trial: TrialNote | None) -> None:
        self._note = note
        self._trial = trial

    @classmethod
    def trial_of(cls, note: CorpusFile) -> BodyTarget:
        return cls(note, TrialNote(note))

    @classmethod
    def corpus_file(cls, note: CorpusFile) -> BodyTarget:
        return cls(note, None)

    def written(self, text: str, fields: dict) -> WrittenBody:
        replaced = self._replaces_a_body()
        destination = self._trial or self._note
        return WrittenBody(destination.write(text, fields), self._trial is not None, replaced)

    def _replaces_a_body(self) -> bool:
        if self._trial is not None:
            return self._trial.exists()
        return self._note.has_body()

    def record(self, report: dict) -> None:
        if self._trial is not None:
            self._trial.write_report(report)

    def record_fields(self, request: ExtractionRequest, mode: str | None) -> dict:
        if self._trial is None:
            return CLEARED_RECORD_FIELDS
        return {**request.record_fields(), EXTRACTION_MODE_FIELD: mode}

    def store_record(self, request: ExtractionRequest, mode: str | None) -> None:
        if self._trial is None:
            ExtractionRecords().write(self._note.basename, ExtractionRecord(request, mode))


class StageCommands:
    def probe(self, args: argparse.Namespace) -> int:
        pdf_path, note = PdfLocator().with_note(args.pdf)
        JsonOutput().emit(ProbeReport(pdf_path, note).as_dict())
        return EXIT_OK

    def extract(self, args: argparse.Namespace) -> int:
        pdf_path, note = PdfLocator().with_note(args.pdf)
        if not (args.replace or args.trial):
            note.require_absent()
        request = ExtractionRequest.from_args(args)
        plan = self.plan_for(pdf_path, request)
        build = self.build(pdf_path, note, request, plan)
        target = BodyTarget.trial_of(note) if args.trial else BodyTarget.corpus_file(note)
        with ConversionSession(plan, TextLayer(pdf_path).page_count()):
            try:
                return self._written(build, request, target)
            except DoubtfulPagesRemain as remaining:
                return self._refuse(pdf_path, remaining)

    def scope(self, args: argparse.Namespace) -> int:
        pdf_path, note = PdfLocator().with_note(args.pdf)
        JsonOutput().emit(ScopeListing(pdf_path, note, tuple(args.page)).as_dict())
        return EXIT_OK

    def convert(self, args: argparse.Namespace) -> int:
        pdf_path, _note = PdfLocator().with_note(args.pdf)
        request = ExtractionRequest((), args.force_ocr, args.force_ocr_pages, args.fresh)
        plan = self.plan_for(pdf_path, request)
        page_count = TextLayer(pdf_path).page_count()
        with ConversionSession(plan, page_count):
            pages = plan.blocks(page_count).pages
        JsonOutput().emit({"pdf": pdf_path.name, "mode": plan.mode, "pages": len(pages)})
        return EXIT_OK

    def layer_sample(self, args: argparse.Namespace) -> int:
        pdf_path, _note = PdfLocator().with_note(args.pdf)
        coverage = LayerCoverage.of_layer(TextLayer(pdf_path))
        JsonOutput().emit(LayerSampleReport(coverage, self._sampled_units(pdf_path, coverage)).as_dict())
        return EXIT_OK

    @staticmethod
    def _sampled_units(pdf_path: Path, coverage: LayerCoverage) -> list[SampleUnit]:
        if not coverage.suffices:
            return []
        with EngineSession():
            return LayerSample.of(pdf_path).sampled_units()

    def labels(self, args: argparse.Namespace) -> int:
        pdf_path, note = PdfLocator().with_note(args.pdf)
        writer = PageLabelWriter(pdf_path, note)
        plan = writer.plan()
        read_back = writer.apply(plan) if args.apply else None
        JsonOutput().emit({**plan, "written": args.apply, "read_back": read_back})
        return EXIT_OK

    def build(self, pdf_path: Path, note: CorpusFile, request: ExtractionRequest,
              plan: ConversionPlan | None = None) -> CorpusBuild:
        spans = GivenScope(request).spans(pdf_path)
        plan = plan or self.plan_for(pdf_path, request)
        return CorpusBuild(BuildInputs(pdf_path, note, plan, self._readings(request), spans))

    def plan_for(self, pdf_path: Path, request: ExtractionRequest) -> ConversionPlan:
        return ConversionPlan(pdf_path, self.options_for(pdf_path, request))

    @staticmethod
    def options_for(pdf_path: Path, request: ExtractionRequest) -> ConversionOptions:
        requested = set(PageRanges().parse(request.forced_pages))
        notation = set() if request.force_ocr else set(NotationPagePlan(pdf_path).pages())
        return ConversionOptions(request.force_ocr, tuple(sorted(requested | notation)), request.fresh,
                                 request.cache_only)

    @staticmethod
    def _readings(request: ExtractionRequest) -> WorkerReadings:
        if request.readings_path is None:
            return WorkerReadings.none()
        return WorkerReadings.load(request.readings_path)

    def _written(self, build: CorpusBuild, request: ExtractionRequest, target: BodyTarget) -> int:
        mode = build.extraction_fields()[EXTRACTION_MODE_FIELD]
        written = target.written(build.rendered().text, target.record_fields(request, mode))
        target.store_record(request, mode)
        report = ExtractReport(build, written).as_dict()
        target.record(report)
        JsonOutput().emit(report)
        return EXIT_OK

    def _refuse(self, pdf_path: Path, remaining: DoubtfulPagesRemain) -> int:
        JsonOutput().emit({"written": None, "reason": str(remaining),
                           "doubtful": DoubtfulReport(pdf_path).as_list(remaining.verdicts)})
        return EXIT_DOUBTFUL

