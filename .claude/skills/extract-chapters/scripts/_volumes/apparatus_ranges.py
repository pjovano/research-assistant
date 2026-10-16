from __future__ import annotations

import re

import vault
from pagetext import TOP_LEVEL

from .document import VolumeDocument
from .extraction import PageRange

BIBLIOGRAPHY_HEADING_RE = re.compile(
    r"^(select(ed)?|general|consolidated|combined|bibliographical|complete)?\s*"
    r"(references?|reference list|bibliography|bibliographie|bibliografia|works cited|literature cited"
    r"|literaturverzeichnis|literaturliste|quellenverzeichnis)$", re.IGNORECASE)
BIBLIOGRAPHY_KIND = "bibliography"
ENDNOTES_KIND = "endnotes"


class ApparatusSection:
    def __init__(self, kind: str, title: str, pages: PageRange) -> None:
        self.kind = kind
        self.title = title
        self.pages = pages

    def covers(self, other: PageRange) -> bool:
        return self.pages.first <= other.last and other.first <= self.pages.last

    def as_json(self) -> dict:
        return {"kind": self.kind, "title": self.title,
                "file_pages": f"{self.pages.first}-{self.pages.last}"}


class VolumeApparatus:
    def __init__(self, volume: VolumeDocument) -> None:
        self._rows = volume.rows_at_or_above(TOP_LEVEL)
        self._kinds = ApparatusKinds()

    def sections(self) -> list[ApparatusSection]:
        found = (self._section_at(index) for index in range(len(self._rows)))
        return [section for section in found if section is not None]

    def _section_at(self, index: int) -> ApparatusSection | None:
        _, title, first_page = self._rows.row(index)
        kind = self._kinds.kind_of(title)
        if kind is None:
            return None
        return ApparatusSection(kind, title.strip(), PageRange(first_page, self._rows.last_page_of(index)))


class ApparatusKinds:
    def kind_of(self, title: str) -> str | None:
        stripped = title.strip()
        if vault.is_notes_heading(stripped):
            return ENDNOTES_KIND
        if BIBLIOGRAPHY_HEADING_RE.match(stripped):
            return BIBLIOGRAPHY_KIND
        return None
