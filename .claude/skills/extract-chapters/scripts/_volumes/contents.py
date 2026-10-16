from __future__ import annotations

import re
from pathlib import Path

import vault
from apparatus import Apparatus

from .apparatus_ranges import ApparatusKinds
from .document import VolumeDocument
from .extraction import PageRange

_NUMBERING_RE = re.compile(
    r"^\s*(?:(?:chapter|part|section)\s+)?(?:[ivxlc]+|\d+)(?:\.\d+)*[.:)\s—–-]+\s*",
    re.IGNORECASE)
_AUTHOR_SEPARATOR_RE = re.compile(r"\s+[—–]\s+")


class ChapterTitle:
    def __init__(self, raw: str) -> None:
        before_author = _AUTHOR_SEPARATOR_RE.split(raw.strip(), maxsplit=1)[0].strip()
        self._heading = _NUMBERING_RE.sub("", before_author).strip() or before_author

    @property
    def heading(self) -> str:
        return self._heading


class Chapter:
    def __init__(self, level: int, title: str, pages: PageRange) -> None:
        self.level = level
        self.title = title
        self.pages = pages
        self._parsed = ChapterTitle(title)

    @property
    def heading(self) -> str:
        return self._parsed.heading

    def as_json(self) -> dict:
        return {"level": self.level, "title": self.title,
                "file_pages": f"{self.pages.first}-{self.pages.last}"}


class VolumeContents:
    def __init__(self, volume: VolumeDocument, max_level: int | None = None) -> None:
        self.basename = volume.basename
        self.page_count = volume.page_count
        self._rows = volume.rows_at_or_above(max_level)
        self._apparatus = Apparatus()
        self._kinds = ApparatusKinds()

    def chapters(self) -> list[Chapter]:
        found = [self._chapter_at(index) for index in range(len(self._rows))]
        return [chapter for chapter in found if not self._is_apparatus(chapter)]

    def _chapter_at(self, index: int) -> Chapter:
        level, title, first_page = self._rows.row(index)
        return Chapter(level, title, PageRange(first_page, self._rows.last_page_of(index)))

    def _is_apparatus(self, chapter: Chapter) -> bool:
        return self._apparatus.is_apparatus(chapter.heading) or self._kinds.kind_of(chapter.title) is not None

    def as_json(self) -> dict:
        return {"volume": self.basename, "page_count": self.page_count,
                "chapters": [chapter.as_json() for chapter in self.chapters()]}


class HeldVolumes:
    def __init__(self) -> None:
        self._directory = vault.VOLUMES_DIR

    def pdfs(self) -> list[Path]:
        return vault.list_pdfs(self._directory)

    def resolve(self, argument: str) -> Path:
        located = vault.locate_pdf(argument, (self._directory,))
        if located is None:
            raise ValueError(f"No volume found for '{argument}' in {self._directory}.")
        return located
