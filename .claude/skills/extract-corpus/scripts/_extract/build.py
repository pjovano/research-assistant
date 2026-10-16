from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from math_fonts import MathFonts
from pagetext import PageClassifier

from _extract.blocks import NOTATION_KINDS, DocumentBlocks
from _extract.cache import MarkerCache
from _extract.checks import (
    REASON_UNREADABLE, SOURCE_EXCLUDED, SOURCE_LAYER, SOURCE_NONE, SOURCE_PIXELS, STATUS_OMITTED, CheckedPage,
    PageChecks, PageVerdict,
)
from _extract.engine import MODE_FORCED_OCR, MODE_TEXT_LAYER, EngineModels, MarkerEngine
from _extract.engineframes import EngineFrames
from _extract.furniture import WorkFurniture
from _extract.hyphens import Hyphens
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.outline import Outline
from _extract.pagefolios import FolioReader, folio_log
from _extract.paths import CorpusFile
from _extract.readings import WorkerReadings
from _extract.request import EXTRACTION_MODE_FIELD
from _extract.policy import SectionPolicy
from _extract.spans import ExcludedSpans
from _extract.structure import NoteStructure, StructureInputs, WorkInputs
from _extract.writer import NoteWriter, Rendered

TITLE_FIELD = "title"


class DoubtfulPagesRemain(RuntimeError):
    def __init__(self, verdicts: list[PageVerdict]) -> None:
        super().__init__(f"{len(verdicts)} doubtful pages remain")
        self.verdicts = verdicts


class ConversionNotCached(RuntimeError):
    pass


@dataclass(frozen=True)
class ConversionOptions:
    force_ocr: bool = False
    forced_pages: tuple[int, ...] = ()
    fresh: bool = False
    cache_only: bool = False


class ConversionPlan:
    def __init__(self, pdf_path: Path, options: ConversionOptions, models: EngineModels | None = None) -> None:
        self._pdf_path = pdf_path
        self._force_ocr = options.force_ocr
        self._forced_pages = list(options.forced_pages)
        self._fresh = options.fresh
        self._cache_only = options.cache_only
        self._models = models or EngineModels()

    @property
    def mode(self) -> str:
        return MODE_FORCED_OCR if self._force_ocr else MODE_TEXT_LAYER

    def reads_pixels(self, file_page: int) -> bool:
        return self._force_ocr or file_page in self._forced_pages

    def blocks(self, page_count: int) -> DocumentBlocks:
        all_pages = list(range(1, page_count + 1))
        frames = EngineFrames(self._pdf_path)
        blocks = frames.placed(self._conversion(self.mode).payload(all_pages), all_pages)
        if self._forced_pass_is_separate():
            forced_payload = self._conversion(MODE_FORCED_OCR).payload(self._forced_pages)
            return blocks.replaced(frames.placed(forced_payload, self._forced_pages).pages)
        return blocks

    def is_cached(self, page_count: int) -> bool:
        if self._fresh:
            return False
        all_pages = list(range(1, page_count + 1))
        cached = MarkerCache(self._pdf_path, self.mode).holds(all_pages)
        if self._forced_pass_is_separate():
            return cached and MarkerCache(self._pdf_path, MODE_FORCED_OCR).holds(self._forced_pages)
        return cached

    def _forced_pass_is_separate(self) -> bool:
        return bool(self._forced_pages) and not self._force_ocr

    def _conversion(self, mode: str) -> PageConversion:
        cache = MarkerCache(self._pdf_path, mode)
        return PageConversion(self._pdf_path, self._engine(mode), FreshConversionCache(cache) if self._fresh else cache)

    def _engine(self, mode: str):
        return RefusedEngine(mode) if self._cache_only else MarkerEngine(self._models, mode)

    @property
    def models(self) -> EngineModels:
        return self._models


class PageConversion:
    def __init__(self, pdf_path: Path, engine, cache) -> None:
        self._pdf_path = pdf_path
        self._engine = engine
        self._cache = cache

    def payload(self, file_pages: list[int]) -> dict:
        missing = self._cache.missing(file_pages)
        if missing:
            self._cache.save(missing, self._engine.convert(self._pdf_path, missing))
        return self._cache.load(file_pages)


class RefusedEngine:
    def __init__(self, mode: str) -> None:
        self._mode = mode

    def convert(self, pdf_path: Path, file_pages: list[int]) -> dict:
        raise ConversionNotCached(f"{pdf_path.name} has no cached {self._mode} conversion of its {len(file_pages)} "
                                  "requested pages, and this build reads only the cache")


class FreshConversionCache:
    def __init__(self, cache: MarkerCache) -> None:
        self._cache = cache

    def missing(self, file_pages: list[int]) -> list[int]:
        return list(file_pages)

    def load(self, file_pages: list[int]) -> dict | None:
        return self._cache.load(file_pages)

    def save(self, file_pages: list[int], payload: dict) -> None:
        self._cache.save(file_pages, payload)


@dataclass(frozen=True)
class BuildInputs:
    pdf_path: Path
    note: CorpusFile
    plan: ConversionPlan
    readings: WorkerReadings
    spans: ExcludedSpans


class CorpusBuild:
    def __init__(self, inputs: BuildInputs) -> None:
        self._pdf_path = inputs.pdf_path
        self._note = inputs.note
        self._plan = inputs.plan
        self._readings = inputs.readings
        self._spans = inputs.spans
        self._layer = TextLayer(inputs.pdf_path)
        self._structure: NoteStructure | None = None
        self._folio_signals: dict = {}
        self._blocks = DocumentBlocks([])
        self._verdicts: list[PageVerdict] | None = None
        self._rendered: Rendered | None = None

    def structure(self) -> NoteStructure:
        if self._structure is None:
            blocks = WorkFurniture(self._layer).refiled(self._plan.blocks(self._layer.page_count()))
            outline = Outline(self._pdf_path).headings()
            inputs = StructureInputs(blocks, outline, self._readings, SectionPolicy(self._spans))
            self._structure = NoteStructure(self._work_inputs(blocks), inputs)
            self._blocks = blocks
        return self._structure

    def notation_blocks(self) -> dict[int, dict[str, int]]:
        self.structure()
        return self._blocks.kind_counts(NOTATION_KINDS)

    def _work_inputs(self, blocks: DocumentBlocks) -> WorkInputs:
        fonts = MathFonts(self._pdf_path)
        title = str(self._note.frontmatter().get(TITLE_FIELD) or "")
        block_html = BlockHtml(Hyphens(self._layer))
        self._folio_signals = FolioReader(self._layer).signals(blocks.pages)
        folios = {file_page: signals.folio for file_page, signals in self._folio_signals.items()}
        return WorkInputs(self._layer, block_html, fonts, title, folios, frozenset(self.pixel_pages()),
                          blocks.furniture_texts, WorkFurniture(self._layer).profile(blocks))

    def folio_log(self) -> list[str]:
        self.structure()
        return folio_log(self._folio_signals)

    def verdicts(self) -> list[PageVerdict]:
        if self._verdicts is None:
            self._verdicts = self._measured()
        return self._verdicts

    def _measured(self) -> list[PageVerdict]:
        texts = self.structure().page_texts()
        omitted = {page: self._omitted_verdict(page, text) for page, text in texts.items()
                   if self._is_unreadable(page)}
        checked = [self._checked_page(page, text) for page, text in texts.items() if page not in omitted]
        measured = {verdict.file_page: verdict for verdict in self._checks().verdicts(checked)}
        return [omitted.get(page) or measured[page] for page in texts]

    def _is_unreadable(self, file_page: int) -> bool:
        reading = self._readings.for_page(file_page)
        return reading is not None and reading.unreadable

    def _checked_page(self, file_page: int, text: str) -> CheckedPage:
        if self._readings.for_page(file_page) is not None:
            return CheckedPage.transcribed(file_page, text)
        return CheckedPage(file_page, text, self.structure().layer_text(file_page), self._source_of(file_page))

    def _source_of(self, file_page: int) -> str:
        if self._plan.reads_pixels(file_page):
            return SOURCE_EXCLUDED if self._spans.covers_page(file_page) else SOURCE_PIXELS
        return SOURCE_LAYER if self._layer.text(file_page).strip() else SOURCE_NONE

    def _checks(self) -> PageChecks:
        return PageChecks(PageClassifier(self._plan.models.ocr_error_model))

    def doubtful(self) -> list[PageVerdict]:
        return [verdict for verdict in self.verdicts() if verdict.is_doubtful]

    def rendered(self) -> Rendered:
        if self.doubtful():
            raise DoubtfulPagesRemain(self.doubtful())
        if self._rendered is None:
            structure = self.structure()
            self._rendered = NoteWriter().render(structure.elements(), structure.definitions())
        return self._rendered

    def pixel_pages(self) -> list[int]:
        return [page for page in range(1, self._layer.page_count() + 1) if self._plan.reads_pixels(page)]

    def extraction_fields(self) -> dict:
        return {EXTRACTION_MODE_FIELD: MODE_FORCED_OCR if self._plan.mode == MODE_FORCED_OCR else None}

    @staticmethod
    def _omitted_verdict(file_page: int, text: str) -> PageVerdict:
        return PageVerdict(file_page, STATUS_OMITTED, REASON_UNREADABLE, text)
