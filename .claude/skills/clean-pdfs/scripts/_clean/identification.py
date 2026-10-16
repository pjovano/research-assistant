from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pymupdf

import vault

from .fontscan import FlaggedCode
from .render import widened
from .sampling import spread
from .textlayer import Occurrences, SuspectOccurrence

GLYPH_RENDER_DPI = 200
LINE_CROP_MARGIN = 30
GLYPHS_DIRECTORY = vault.GLYPHS_DIRECTORY
IDENTIFY_SAMPLES = 3
IMAGE_SUFFIX = ".png"
FIRST_RENDER = 1


@dataclass(frozen=True)
class RenderRequest:
    page: int
    line_bbox: tuple[float, float, float, float]
    name: str


class GlyphRenders:
    def __init__(self, pdf_path: Path, directory: Path, dpi: int = GLYPH_RENDER_DPI) -> None:
        self._path = pdf_path
        self._directory = directory
        self._dpi = dpi

    def paths_for(self, requests: list[RenderRequest]) -> list[Path]:
        return [self._destination(request) for request in requests]

    def save(self, requests: list[RenderRequest]) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        with pymupdf.open(self._path) as doc:
            for request in requests:
                self._save_one(doc, request)

    def _save_one(self, doc: pymupdf.Document, request: RenderRequest) -> None:
        page = doc[request.page]
        clip = widened(pymupdf.Rect(*request.line_bbox), LINE_CROP_MARGIN, LINE_CROP_MARGIN) & page.rect
        page.get_pixmap(dpi=self._dpi, clip=clip).save(self._destination(request))

    def _destination(self, request: RenderRequest) -> Path:
        return self._directory / f"{request.name}{IMAGE_SUFFIX}"


class SampledOccurrences:
    def __init__(self, found: list[SuspectOccurrence], limit: int = IDENTIFY_SAMPLES) -> None:
        self._found = found
        self._limit = limit

    def pick(self) -> list[SuspectOccurrence]:
        return spread(self._found, self._limit)


class FontIdentification:
    def __init__(self, codes: list[FlaggedCode], occurrences: Occurrences, renders: GlyphRenders) -> None:
        self._codes = codes
        self._occurrences = occurrences
        self._renders = renders
        self._rendered: Counter = Counter()

    def report(self) -> list[dict]:
        return [self._entry(group) for group in _grouped_by_identity(self._codes)]

    def _entry(self, group: list[FlaggedCode]) -> dict:
        lead = group[0]
        found = self._occurrences_of(group)
        rows = self._rendered_rows(lead, SampledOccurrences(found).pick())
        return {**lead.as_row(len(found)), "xrefs": [flagged.record.xref for flagged in group], "samples": rows}

    def _occurrences_of(self, group: list[FlaggedCode]) -> list[SuspectOccurrence]:
        return [found for flagged in group for found in self._occurrences.of(flagged.record, flagged.char)]

    def _rendered_rows(self, lead: FlaggedCode, samples: list[SuspectOccurrence]) -> list[dict]:
        names = self._claim_names(lead, len(samples))
        requests = [RenderRequest(sample.page, sample.line_bbox, name) for sample, name in zip(samples, names)]
        self._renders.save(requests)
        return [_sample_row(sample, path) for sample, path in zip(samples, self._renders.paths_for(requests))]

    def _claim_names(self, flagged: FlaggedCode, count: int) -> list[str]:
        family, code = _render_key(flagged)
        first = self._rendered[(family, code)] + FIRST_RENDER
        self._rendered[(family, code)] += count
        return [f"{family}-{code}-{number}" for number in range(first, first + count)]


def _render_key(flagged: FlaggedCode) -> tuple[str, str]:
    return flagged.record.family, flagged.code


def _grouped_by_identity(codes: list[FlaggedCode]) -> list[list[FlaggedCode]]:
    groups: dict[tuple[str, str, str], list[FlaggedCode]] = {}
    for flagged in codes:
        if not flagged.is_resolved():
            groups.setdefault(flagged.identity_key(), []).append(flagged)
    return list(groups.values())


def _sample_row(sample: SuspectOccurrence, path: Path) -> dict:
    return {"page": sample.page_number, "render": str(path), "context": sample.context}
