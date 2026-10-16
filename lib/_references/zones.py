from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

import pagetext
import vault
from apparatus import INDEX_NAME_PATTERN
from scratch_cache import ScratchCache

BIBLIOGRAPHY = "bibliography"
NOTES = "notes"
ABSENT = "absent"

_INDEX_LINE_RE = re.compile(rf"^\s*(?:\d+\s*)?(?:{INDEX_NAME_PATTERN})\s*(?:\d+\s*)?$", re.IGNORECASE)

TAIL_FRACTION = 0.5

MAX_ZONE_PAGES = 80

RUN_GAP_PAGES = 3

ZONE_CACHE_NAME = "reference-zone.json"


@dataclass(frozen=True)
class ReferenceZone:
    method: str
    first_page: int
    last_page: int
    text: str

    @property
    def is_present(self) -> bool:
        return self.method != ABSENT


class _PageLines:
    def __init__(self, text: str) -> None:
        self._lines = text.splitlines()

    def any_match(self, test: Callable[[str], bool]) -> bool:
        return any(test(line) for line in self._lines)


class SectionHeading:
    def __init__(self, test: Callable[[str], bool]) -> None:
        self._test = test

    @classmethod
    def of_bibliography(cls) -> SectionHeading:
        return cls(vault.is_bibliography_heading)

    @classmethod
    def of_notes(cls) -> SectionHeading:
        return cls(vault.names_notes_section)

    def matches(self, text: str) -> bool:
        return self._test(text)

    def on_page(self, text: str) -> bool:
        return _PageLines(text).any_match(self.matches)


class ZoneLocator:
    def __init__(self, pdf_path: Path) -> None:
        self._pdf_path = pdf_path
        self._tests = ((SectionHeading.of_bibliography(), BIBLIOGRAPHY), (SectionHeading.of_notes(), NOTES))

    def locate(self) -> ReferenceZone:
        records = pagetext.page_records(self._pdf_path)
        for test, method in self._tests:
            start = self._outline_start(test) or self._scanned_start(records, test)
            if start:
                return self._zone(records, start, method)
        return ReferenceZone(ABSENT, 0, 0, "")

    def _outline_start(self, test: SectionHeading) -> int | None:
        outline = pagetext.outline_entries(self._pdf_path)
        return self._last_run_start(sorted(page for _level, title, page in outline if test.matches(title)))

    def _scanned_start(self, records: list[pagetext.PageRecord], test: SectionHeading) -> int | None:
        floor = int(len(records) * TAIL_FRACTION)
        return self._last_run_start([record.pdf_page for record in records[floor:] if test.on_page(record.text)])

    def _last_run_start(self, pages: list[int]) -> int | None:
        runs = self._runs(pages)
        return runs[-1][0] if runs else None

    def _runs(self, pages: list[int]) -> list[list[int]]:
        runs: list[list[int]] = []
        for page in pages:
            if runs and page - runs[-1][-1] <= RUN_GAP_PAGES:
                runs[-1].append(page)
            else:
                runs.append([page])
        return runs

    def _zone(self, records: list[pagetext.PageRecord], start: int, method: str) -> ReferenceZone:
        end = self._closing_page(records, start)
        pages = [record for record in records if start <= record.pdf_page <= end]
        return ReferenceZone(method, start, end, "\n".join(record.text for record in pages))

    def _closing_page(self, records: list[pagetext.PageRecord], start: int) -> int:
        limit = min(len(records), start + MAX_ZONE_PAGES - 1)
        for record in records:
            if record.pdf_page > start and self._closes(record.text):
                return min(record.pdf_page - 1, limit)
        return limit

    def _closes(self, text: str) -> bool:
        return any(_INDEX_LINE_RE.match(line.strip()) for line in text.splitlines())


class ZoneCache:
    def __init__(self, pdf_path: Path) -> None:
        self._pdf_path = pdf_path
        self._file = ScratchCache(vault.SCRATCH_DIR / pdf_path.stem / ZONE_CACHE_NAME)

    def loaded(self) -> ReferenceZone | None:
        entry = self._file.entry()
        if entry is None or entry.get("fingerprint") != self._fingerprint():
            return None
        return self._zone(entry.get("zone"))

    def save(self, zone: ReferenceZone) -> None:
        self._file.save({"fingerprint": self._fingerprint(), "zone": asdict(zone)})

    @staticmethod
    def _zone(fields: dict | None) -> ReferenceZone | None:
        try:
            return ReferenceZone(**fields)
        except TypeError:
            return None

    def _fingerprint(self) -> list:
        return list(pagetext.document_fingerprint(self._pdf_path))


class CachedZone:
    def __init__(self, pdf_path: Path) -> None:
        self._cache = ZoneCache(pdf_path)
        self._locator = ZoneLocator(pdf_path)

    def locate(self) -> ReferenceZone:
        loaded = self._cache.loaded()
        if loaded is not None:
            return loaded
        zone = self._locator.locate()
        self._cache.save(zone)
        return zone
