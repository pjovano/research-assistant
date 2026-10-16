from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from pathlib import Path

from _extract.blocks import DocumentBlocks, PageBlocks
from _extract.build import PageConversion
from _extract.cache import MarkerCache
from _extract.console import FORCE_OCR_FLAG
from _extract.engine import MODE_FORCED_OCR, EngineModels, MarkerEngine
from _extract.enginemath import MATH_ELEMENT_RE
from _extract.layer import TextLayer
from _extract.outline import Outline
from _extract.pixelchapters import PixelChapters
from _extract.ranges import PageRanges
from _extract.request import FORCE_OCR_PAGES_FLAG
from _extract.scanlayer import READS_LAYER, READS_PIXELS, LayerCoverage
from _extract.wordagreement import WordSequence

LAYER_SAMPLE_MODE = "layer-sample"
MIN_UNIT_PAGES = 20
SAMPLES_PER_UNIT = 3
MIN_SAMPLE_WORDS = 80
MIN_AGREEMENT = 0.93
MIN_NOTATION_SPANS = 5
AGREEMENT_PRECISION = 3


@dataclass(frozen=True)
class SampleReading:
    file_page: int
    agreement: float
    notation_spans: int

    @property
    def agrees(self) -> bool:
        return self.agreement >= MIN_AGREEMENT and self.notation_spans < MIN_NOTATION_SPANS

    def as_dict(self) -> dict:
        return {"file_page": self.file_page, "agreement": round(self.agreement, AGREEMENT_PRECISION),
                "notation_spans": self.notation_spans}


@dataclass(frozen=True)
class SampleUnit:
    pages: range
    readings: tuple[SampleReading, ...]

    @property
    def reads_layer(self) -> bool:
        return bool(self.readings) and all(reading.agrees for reading in self.readings)

    def as_dict(self) -> dict:
        return {"first": self.pages.start, "last": self.pages.stop - 1,
                "reads": READS_LAYER if self.reads_layer else READS_PIXELS,
                "samples": [reading.as_dict() for reading in self.readings]}


class SampleUnits:
    def __init__(self, chapters: list[range]) -> None:
        self._chapters = chapters

    def units(self) -> list[range]:
        units: list[range] = []
        start: int | None = None
        for chapter in self._chapters:
            start = chapter.start if start is None else start
            if chapter.stop - start >= MIN_UNIT_PAGES:
                units.append(range(start, chapter.stop))
                start = None
        return self._with_remainder(units, start)

    def _with_remainder(self, units: list[range], start: int | None) -> list[range]:
        if start is None:
            return units
        stop = self._chapters[-1].stop
        if not units:
            return [range(start, stop)]
        return [*units[:-1], range(units[-1].start, stop)]


class SamplePages:
    def __init__(self, layer: TextLayer) -> None:
        self._layer = layer

    def of(self, unit: range) -> list[int]:
        eligible = [page for page in unit if self.words_on(page).count >= MIN_SAMPLE_WORDS]
        count = min(SAMPLES_PER_UNIT, len(eligible))
        return [eligible[(2 * index + 1) * len(eligible) // (2 * count)] for index in range(count)]

    def words_on(self, file_page: int) -> WordSequence:
        return WordSequence(self._layer.text(file_page))


class PixelPage:
    def __init__(self, page: PageBlocks) -> None:
        self._blocks = page.blocks

    @property
    def words(self) -> WordSequence:
        prose = [dataclasses.replace(block, html=MATH_ELEMENT_RE.sub(" ", block.html)).plain_text
                 for block in self._blocks]
        return WordSequence(" ".join(prose))

    @property
    def notation_spans(self) -> int:
        return sum(len(MATH_ELEMENT_RE.findall(block.html)) for block in self._blocks)


class PixelSampleReader:
    def __init__(self, pdf_path: Path, engine) -> None:
        self._pdf_path = pdf_path
        self._engine = engine

    def pages(self, file_pages: list[int]) -> dict[int, PageBlocks]:
        if not file_pages:
            return {}
        cache = MarkerCache(self._pdf_path, LAYER_SAMPLE_MODE)
        payload = PageConversion(self._pdf_path, self._engine, cache).payload(file_pages)
        return {page.file_page: page for page in DocumentBlocks.from_json(payload, file_pages).pages}


class LayerSample:
    def __init__(self, layer: TextLayer, units: list[range], reader: PixelSampleReader) -> None:
        self._pages = SamplePages(layer)
        self._units = units
        self._reader = reader

    @classmethod
    def of(cls, pdf_path: Path) -> LayerSample:
        layer = TextLayer(pdf_path)
        headings = [{"level": heading.level, "file_page": heading.file_page}
                    for heading in Outline(pdf_path).headings()]
        units = SampleUnits(PixelChapters(headings, layer.page_count()).chapters()).units()
        return cls(layer, units, PixelSampleReader(pdf_path, MarkerEngine(EngineModels(), MODE_FORCED_OCR)))

    def sampled_units(self) -> list[SampleUnit]:
        picks = [(unit, self._pages.of(unit)) for unit in self._units]
        read = self._reader.pages(sorted(page for _unit, pages in picks for page in pages))
        return [SampleUnit(unit, tuple(self._reading(page, read.get(page, PageBlocks(page, []))) for page in pages))
                for unit, pages in picks]

    def _reading(self, file_page: int, pixel_page: PageBlocks) -> SampleReading:
        pixels = PixelPage(pixel_page)
        agreement = self._pages.words_on(file_page).agreement_with(pixels.words)
        return SampleReading(file_page, agreement, pixels.notation_spans)


class LayerSampleReport:
    def __init__(self, coverage: LayerCoverage, units: list[SampleUnit]) -> None:
        self._coverage = coverage
        self._units = units

    def as_dict(self) -> dict:
        pixel_pages = self._pixel_pages()
        return {"reads": self._reading(), "pixel_pages": pixel_pages, "flags": self._flags(pixel_pages),
                "pages_with_text": self._coverage.pages_with_text, "page_count": self._coverage.page_count,
                "units": [unit.as_dict() for unit in self._units]}

    def _reading(self) -> str:
        return READS_LAYER if any(unit.reads_layer for unit in self._units) else READS_PIXELS

    def _pixel_pages(self) -> str | None:
        pages = [page for unit in self._units if not unit.reads_layer for page in unit.pages]
        return PageRanges().compact(pages) if pages and self._reading() == READS_LAYER else None

    def _flags(self, pixel_pages: str | None) -> list[str]:
        if self._reading() == READS_PIXELS:
            return [FORCE_OCR_FLAG]
        return [FORCE_OCR_PAGES_FLAG, pixel_pages] if pixel_pages else []
