from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import pagetext
import vault
from _vault.naming import nfc
from _vault.scratch import ENGINE_COSTS_NAME

from _drive.work import STATE_NAME, WORKS_NAME
from _extract.backfillprep import FONTS_CHECKED_FIELD, PIXEL_PAGES_FIELD, PIXELS_ONLY_FIELD, ScanReading
from _extract.layer import TextLayer
from _extract.notationpages import NotationPagePlan
from _extract.ranges import PageRanges
from _extract.report import reads_as_scan

FINGERPRINT_FIELD = "fingerprint"
PAGES_FIELD = "pages"
SCANNED_FIELD = "scanned"
NOTATION_PAGES_FIELD = "notation_pages"
UNKNOWN = math.inf
TEXT_PAGES_PER_PIXEL_PAGE = 100


@dataclass(frozen=True)
class EngineCost:
    pixel_pages: float
    pages: float

    def __lt__(self, other: EngineCost) -> bool:
        return self._rank < other._rank

    @property
    def is_known(self) -> bool:
        return UNKNOWN not in (self.pixel_pages, self.pages)

    @property
    def engine_time(self) -> float:
        if not self.is_known:
            return UNKNOWN
        text_pages = max(self.pages - self.pixel_pages, 0)
        return self.pixel_pages * TEXT_PAGES_PER_PIXEL_PAGE + text_pages

    @property
    def _rank(self) -> tuple[float, float]:
        return self.engine_time, self.pages

    def as_list(self) -> list[int] | None:
        if not self.is_known:
            return None
        return [int(self.engine_time), int(self.pages)]


UNKNOWN_COST = EngineCost(UNKNOWN, UNKNOWN)


@dataclass(frozen=True)
class PdfReading:
    pages: int
    scanned: bool
    notation_pages: frozenset[int]

    @classmethod
    def of(cls, pdf_path: Path) -> PdfReading:
        layer = TextLayer(pdf_path)
        scanned = reads_as_scan(layer)
        notation = frozenset() if scanned else frozenset(NotationPagePlan(pdf_path).pages())
        return cls(layer.page_count(), scanned, notation)

    @classmethod
    def from_entry(cls, entry: dict) -> PdfReading:
        notation = frozenset(PageRanges().parse(entry.get(NOTATION_PAGES_FIELD) or ""))
        return cls(int(entry[PAGES_FIELD]), bool(entry[SCANNED_FIELD]), notation)

    def entry(self, fingerprint: list) -> dict:
        return {FINGERPRINT_FIELD: fingerprint, PAGES_FIELD: self.pages, SCANNED_FIELD: self.scanned,
                NOTATION_PAGES_FIELD: PageRanges().compact(sorted(self.notation_pages))}


class FontRecord:
    def __init__(self, state: dict) -> None:
        self._state = state

    @classmethod
    def of_backfill_work(cls, backfill_dir: Path, pdf_path: Path) -> FontRecord:
        state_path = backfill_dir / WORKS_NAME / nfc(vault.basename_of(pdf_path)) / STATE_NAME
        try:
            return cls(json.loads(state_path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return cls({})

    @property
    def is_settled(self) -> bool:
        return bool(self._state.get(FONTS_CHECKED_FIELD) or self._state.get(PIXELS_ONLY_FIELD))

    def scan_reading(self, scanned: bool) -> ScanReading:
        return ScanReading(scanned, self._state)

    @property
    def pixel_pages_listing(self) -> str | None:
        return self._state.get(PIXEL_PAGES_FIELD)

    @property
    def pixel_pages(self) -> frozenset[int]:
        return frozenset(PageRanges().parse(self.pixel_pages_listing or ""))


class EngineCosts:
    def __init__(self, cache_path: Path | None = None, read=PdfReading.of) -> None:
        self._cache_path = cache_path or vault.SCRATCH_DIR / ENGINE_COSTS_NAME
        self._read = read
        self._entries: dict | None = None

    def of(self, pdf_path: Path, record: FontRecord) -> EngineCost:
        try:
            reading = self._reading(pdf_path)
        except (OSError, RuntimeError, ValueError):
            return UNKNOWN_COST
        if record.scan_reading(reading.scanned).reads_every_page_from_pixels:
            return EngineCost(reading.pages, reading.pages)
        return EngineCost(len(reading.notation_pages | record.pixel_pages), reading.pages)

    def _reading(self, pdf_path: Path) -> PdfReading:
        key = nfc(vault.basename_of(pdf_path))
        fingerprint = list(pagetext.document_fingerprint(pdf_path))
        entry = self._loaded().get(key)
        if entry and entry.get(FINGERPRINT_FIELD) == fingerprint:
            return PdfReading.from_entry(entry)
        reading = self._read(pdf_path)
        self._loaded()[key] = reading.entry(fingerprint)
        self._save()
        return reading

    def _loaded(self) -> dict:
        if self._entries is None:
            try:
                self._entries = json.loads(self._cache_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self._entries = {}
        return self._entries

    def _save(self) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        partial = self._cache_path.with_suffix(".json.part")
        partial.write_text(json.dumps(self._loaded(), ensure_ascii=False), encoding="utf-8")
        partial.replace(self._cache_path)


class CheapestFirst:
    def __init__(self, costs: EngineCosts, located, record_of) -> None:
        self._costs = costs
        self._located = located
        self._record_of = record_of

    @classmethod
    def for_backfill(cls, backfill_dir: Path, costs: EngineCosts | None = None,
                     directories: tuple[Path, ...] | None = None) -> CheapestFirst:
        searched = directories or (vault.LIBRARY_DIR,)
        return cls(costs or EngineCosts(), lambda pdf: vault.locate_pdf(pdf, searched),
                   lambda path: FontRecord.of_backfill_work(backfill_dir, path))

    def ordered(self, pdfs: list[str]) -> list[str]:
        costed = [(self.cost(pdf), position, pdf) for position, pdf in enumerate(pdfs)]
        return [pdf for _cost, _position, pdf in sorted(costed)]

    def cost(self, pdf: str) -> EngineCost:
        path = self._located(pdf)
        return UNKNOWN_COST if path is None else self._costs.of(path, self._record_of(path))
