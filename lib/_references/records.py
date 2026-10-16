from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from _references.entries import EntryParser, ReferenceEntry
from _references.zones import ReferenceZone, ZoneLocator


@dataclass(frozen=True)
class ReferenceRecord:
    basename: str
    method: str
    first_page: int
    last_page: int
    text: str
    entries: list[ReferenceEntry]


class ReferenceExtractor:
    def __init__(self) -> None:
        self._parser = EntryParser()

    def extract(self, pdf_path: Path) -> ReferenceRecord:
        return self.of_zone(pdf_path.stem, ZoneLocator(pdf_path).locate())

    def of_zone(self, basename: str, zone: ReferenceZone) -> ReferenceRecord:
        entries = self._parser.parse(zone.text) if zone.is_present else []
        return ReferenceRecord(basename, zone.method, zone.first_page, zone.last_page,
                               zone.text, entries)
