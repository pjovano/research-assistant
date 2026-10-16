from __future__ import annotations

import re
import textwrap
from pathlib import Path
from typing import Protocol

import vault
from page_marker import PageMarker

from _extract.cleanuppages import CleanupPages, pages_running_on
from _extract.correctiontext import NOTES_SECTION_OPENING, DEFINITION_OPENING
from _extract.layer import TextLayer
from _extract.outline import Outline
from _extract.ranges import PageRanges
from _extract.scope import WORK_FIELDS
from _extract.trial import TRIALS_DIR_NAME

LAYER_LINES_SUFFIX = ".layer-lines.txt"
PAGES_FILE_SUFFIX = ".cleanup-pages.md"
PAGE_HEADER = "=== file page {page} ==="
WRAP_COLUMNS = 160
_MARK_RE = re.compile(r"\[\^([^\]\s]+)\](?!:)")
_DEFINITION_RE = re.compile(r"^\[\^([^\]\s]+)\]:")
_ENCODING = "utf-8"


class ListedText(Protocol):
    @property
    def basename(self) -> str: ...

    @property
    def path(self) -> Path: ...

    def body(self) -> str: ...

    def report(self) -> dict: ...

    def excluded(self) -> tuple[tuple[str, str], ...]: ...


class CorrectionListing:
    def __init__(self, pdf_path: Path, listed: ListedText) -> None:
        self._pdf_path = pdf_path
        self._listed = listed
        body, self._definitions = _split_notes(listed.body())
        self._slices = PageMarker.sliced(body)
        self._running_on = pages_running_on(body)
        self._markers = {marker.file_page: marker.comment() for marker in PageMarker.inline(body)}

    def as_dict(self) -> dict:
        flagged = CleanupPages(self._slices, self._listed.report(), self._running_on).flagged()
        lines_path = LayerLinesFile(TextLayer(self._pdf_path), self._pixel_pages()).written(self._listed.basename,
                                                                                            sorted(flagged))
        pages_file = PagesFile(self._listed.basename)
        pages = [self._page(page, reasons, pages_file.add(page, self._slices[page]))
                 for page, reasons in flagged.items()]
        return {"work": self._work(), "text": str(self._listed.path), "pages_file": str(pages_file.written()),
                "layer_lines": str(lines_path),
                "headings": [{"level": heading.level, "title": heading.title, "file_page": heading.file_page}
                             for heading in Outline(self._pdf_path).headings()],
                "scope": [{"start": start, "resume": resume} for start, resume in self._listed.excluded()],
                "pages": pages, "notes": self._cited_notes(list(flagged))}

    def _page(self, page: int, reasons: list[str], lines: tuple[int, int]) -> dict:
        return {"file_page": page, "marker": self._markers.get(page), "flags": reasons, "lines": list(lines)}

    def _work(self) -> dict:
        meta = vault.read_frontmatter_only(vault.CORPUS_DIR / f"{self._listed.basename}.md")
        return {field: meta.get(field) for field in WORK_FIELDS}

    def _pixel_pages(self) -> frozenset[int]:
        return frozenset(PageRanges().parse(self._listed.report().get("read_from_pixels") or ""))

    def _cited_notes(self, pages: list[int]) -> list[str]:
        cited = {label for page in pages for label in _MARK_RE.findall(self._slices[page])}
        kept, label = [], None
        for line in self._definitions:
            opening = _DEFINITION_RE.match(line)
            label = opening.group(1) if opening else label
            if label in cited:
                kept.append(line)
        return kept


class PagesFile:
    def __init__(self, basename: str) -> None:
        self._path = vault.SCRATCH_DIR / TRIALS_DIR_NAME / f"{basename}{PAGES_FILE_SUFFIX}"
        self._lines: list[str] = []

    def add(self, page: int, text: str) -> tuple[int, int]:
        first = len(self._lines) + 1
        self._lines.append(PAGE_HEADER.format(page=page))
        for line in text.splitlines():
            self._lines += textwrap.wrap(line, WRAP_COLUMNS, break_long_words=False, break_on_hyphens=False) or [""]
        return first, len(self._lines)

    def written(self) -> Path:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text("\n".join(self._lines) + "\n", encoding=_ENCODING)
        return self._path


class LayerLinesFile:
    def __init__(self, layer: TextLayer, pixel_pages: frozenset[int]) -> None:
        self._layer = layer
        self._pixel_pages = pixel_pages

    def written(self, basename: str, pages: list[int]) -> Path:
        path = vault.SCRATCH_DIR / TRIALS_DIR_NAME / f"{basename}{LAYER_LINES_SUFFIX}"
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [line for page in pages if self._is_restorable(page) for line in self._numbered(page)]
        path.write_text("\n".join(lines) + "\n", encoding=_ENCODING)
        return path

    def _is_restorable(self, page: int) -> bool:
        return page not in self._pixel_pages and self._layer.has_text(page) and self._layer.is_drawn(page)

    def _numbered(self, page: int) -> list[str]:
        return [f"p{page}.{number}: {line.text}" for number, line in enumerate(self._layer.lines(page), start=1)]


def _split_notes(body: str) -> tuple[str, list[str]]:
    start = body.rfind(NOTES_SECTION_OPENING + DEFINITION_OPENING)
    if start < 0:
        return body, []
    notes = body[start + len(NOTES_SECTION_OPENING):]
    return body[:start], [line for line in notes.splitlines() if line.strip()]
