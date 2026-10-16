from __future__ import annotations

import json
import re
from pathlib import Path

from _drive.work import SetAside, WorkDirectory, WorkStops
from _extract.backfillrunner import ExtractScript
from _extract.backfillscope import ScopeDispatch
from _extract.console import FORCE_OCR_FLAG
from _extract.ranges import PageRanges
from _extract.request import FORCE_OCR_PAGES_FLAG
from _extract.scanlayer import READS_LAYER, READS_PIXELS, LayerCoverage

OUTLINE_FREE_TYPES = ("journalArticle", "bookSection")
BOOK_TYPES = ("book", "thesis")
BOOK_KIND = "book"
ARTICLE_KIND = "article"
FRONTMATTER_FENCE = "---"
TYPE_FIELD = re.compile(r"^type:\s*['\"]?([A-Za-z]+)", re.M)
FONTS_CHECKED_FIELD = "fonts_checked"
PIXELS_ONLY_FIELD = "pixels_only"
PIXEL_PAGES_FIELD = "pixel_pages"
PIXEL_PAGES_STATE = "pixel-pages"
ONE_CHAPTER_FIELD = "one_chapter"
CLEANUP_FIELD = "cleanup"
LAYER_SAMPLE_FIELD = "layer_sample"
KEPT_FIELDS = (PIXELS_ONLY_FIELD, PIXEL_PAGES_FIELD, ONE_CHAPTER_FIELD, CLEANUP_FIELD, LAYER_SAMPLE_FIELD)
STATE_UNBOOKMARKED = "unbookmarked"
SCANNED_FIELD = "scanned"
LAYER_SAMPLE_NAME = "layer-sample.json"
SAMPLE_READS_KEY = "reads"
SAMPLE_PIXEL_PAGES_KEY = "pixel_pages"


def frontmatter_type(note: Path) -> str | None:
    text = note.read_text()
    head = text.split("\n" + FRONTMATTER_FENCE, 2)[0] if text.startswith(FRONTMATTER_FENCE) else ""
    match = TYPE_FIELD.search(head)
    return match.group(1) if match else None


def bookmarking_kind(item_type: str) -> str:
    return BOOK_KIND if item_type in BOOK_TYPES else ARTICLE_KIND


class Preparation:
    def __init__(self, work: WorkDirectory, script: ExtractScript) -> None:
        self._work = work
        self._script = script

    def run(self) -> dict:
        probe = self._script.checked("probe", self._work.pdf).payload()
        self._work.save("probe.json", probe)
        if probe.get("reviewed") or probe.get("body_exists"):
            return {"state": "skip"}
        state = self._work.state()
        if not (state.get(FONTS_CHECKED_FIELD) or state.get(PIXELS_ONLY_FIELD)):
            return {"state": "fonts"}
        self._require_outline(probe, state)
        state = self._layer_sampled(probe, state)
        flags = conversion_flags(probe, state)
        kept = {field: state[field] for field in KEPT_FIELDS if field in state}
        self._work.save_state({**kept, FONTS_CHECKED_FIELD: True, "flags": flags, "scope_runs": 0})
        self._script.checked("convert", self._work.pdf, *flags)
        dispatch = ScopeDispatch(self._work)
        dispatch.write(self._script.checked("scope", self._work.pdf).stdout)
        return {"state": "ready", "parts": dispatch.dispatch(0)}

    def record_fonts_checked(self) -> dict:
        self._work.save_state({**self._work.state(), FONTS_CHECKED_FIELD: True})
        return {"state": "fonts-checked"}

    def record_pixels_only(self) -> dict:
        self._work.save_state({**self._work.state(), PIXELS_ONLY_FIELD: True})
        return {"state": "pixels-only"}

    def record_pixel_pages(self, listing: Path) -> dict:
        ranges = PageRanges().compact(PixelPagesListing(listing).pages())
        self._work.save_state({**self._work.state(), PIXEL_PAGES_FIELD: ranges})
        return {"state": PIXEL_PAGES_STATE, PIXEL_PAGES_FIELD: ranges}

    def record_cleanup(self, cleanup: bool) -> dict:
        self._work.save_state({**self._work.state(), CLEANUP_FIELD: cleanup})
        return {"state": "cleanup-recorded", CLEANUP_FIELD: cleanup}

    def record_one_chapter(self) -> dict:
        self._work.save_state({**self._work.state(), ONE_CHAPTER_FIELD: True})
        return {"state": "one-chapter"}

    def _layer_sampled(self, probe: dict, state: dict) -> dict:
        if not ScanReading.of_probe(probe, state).awaits_layer_sample(LayerCoverage.of_probe(probe)):
            return state
        sample = self._script.checked("layer-sample", self._work.pdf).payload()
        self._work.save(LAYER_SAMPLE_NAME, sample)
        sampled = LayerSampleRecord(sample).recorded_in(state)
        self._work.save_state(sampled)
        return sampled

    def _require_outline(self, probe: dict, state: dict) -> None:
        if probe["headings"] or state.get(ONE_CHAPTER_FIELD):
            return
        kind = frontmatter_type(Path(probe["corpus_file"]))
        if kind is None:
            raise SetAside("the frontmatter names no type:")
        if kind not in OUTLINE_FREE_TYPES:
            raise WorkStops(STATE_UNBOOKMARKED, question=f"a {kind} with no outline", kind=bookmarking_kind(kind),
                            pixels_only=bool(state.get(PIXELS_ONLY_FIELD) or state.get(PIXEL_PAGES_FIELD)))


class PixelPagesListing:
    def __init__(self, path: Path) -> None:
        self._path = path

    def pages(self) -> list[int]:
        try:
            pages = json.loads(self._path.read_text(encoding="utf-8"))["pages"]
        except (OSError, ValueError, KeyError, TypeError):
            raise SetAside(f"the pixel pages listing {self._path} names no pages") from None
        if not pages or not all(isinstance(page, int) for page in pages):
            raise SetAside(f"the pixel pages listing {self._path} names no pages")
        return pages


class ScanReading:
    def __init__(self, scanned: bool, state: dict) -> None:
        self._scanned = scanned
        self._state = state

    @classmethod
    def of_probe(cls, probe: dict, state: dict) -> ScanReading:
        return cls(bool(probe.get(SCANNED_FIELD)), state)

    @property
    def reads_every_page_from_pixels(self) -> bool:
        return self._is_pixels_only or (self._scanned and self._state.get(LAYER_SAMPLE_FIELD) != READS_LAYER)

    def awaits_layer_sample(self, coverage: LayerCoverage) -> bool:
        unsampled = LAYER_SAMPLE_FIELD not in self._state
        return self._scanned and unsampled and not self._is_pixels_only and coverage.suffices

    @property
    def _is_pixels_only(self) -> bool:
        return bool(self._state.get(PIXELS_ONLY_FIELD))


class LayerSampleRecord:
    def __init__(self, sample: dict) -> None:
        self._sample = sample

    def recorded_in(self, state: dict) -> dict:
        recorded = {**state, LAYER_SAMPLE_FIELD: self._reading()}
        pages = PageRanges().parse(state.get(PIXEL_PAGES_FIELD)) + PageRanges().parse(self._pixel_pages())
        if pages:
            recorded[PIXEL_PAGES_FIELD] = PageRanges().compact(pages)
        return recorded

    def _reading(self) -> str:
        reading = self._sample.get(SAMPLE_READS_KEY)
        if reading not in (READS_LAYER, READS_PIXELS):
            raise SetAside(f"the layer sample names no reading: {self._sample!r}")
        return reading

    def _pixel_pages(self) -> str | None:
        pages = self._sample.get(SAMPLE_PIXEL_PAGES_KEY)
        return pages if self._reading() == READS_LAYER and isinstance(pages, str) else None


def conversion_flags(probe: dict, state: dict) -> list[str]:
    if ScanReading.of_probe(probe, state).reads_every_page_from_pixels:
        return [FORCE_OCR_FLAG]
    if state.get(PIXEL_PAGES_FIELD):
        return [FORCE_OCR_PAGES_FLAG, state[PIXEL_PAGES_FIELD]]
    return []
