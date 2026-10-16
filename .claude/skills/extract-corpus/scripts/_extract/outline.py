from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from _pagetext.pages import outline_title

from _extract.pagetitles import PageTitles

PAGE_TOP = 0.0
DESTINATION_EDGE_TOLERANCE = 1.0


@dataclass(frozen=True)
class Heading:
    level: int
    title: str
    file_page: int
    position: float = PAGE_TOP


class Outline:
    def __init__(self, pdf_path: Path) -> None:
        self._pdf_path = pdf_path

    def headings(self) -> list[Heading]:
        with pymupdf.open(self._pdf_path) as document:
            entries = self._divisions([entry for entry in document.get_toc(simple=False) or [] if self._is_placed(entry)])
            headings = [self._heading(document, entry) for entry in entries]
        if self._names_one_depth_for_every_entry(entries):
            headings = [dataclasses.replace(heading, position=PAGE_TOP) for heading in headings]
        return sorted(headings, key=lambda heading: (heading.file_page, heading.position))

    @staticmethod
    def _is_placed(entry: list) -> bool:
        _level, _title, page, _details = entry
        return int(page) >= 1

    def _divisions(self, placed: list) -> list:
        titles = [(outline_title(str(title)), int(page)) for _level, title, page, _details in placed]
        page_titles = PageTitles(self._pdf_path, titles)
        return [entry for entry, (title, _page) in zip(placed, titles) if not page_titles.names_a_page(title)]

    @staticmethod
    def _names_one_depth_for_every_entry(entries: list) -> bool:
        destinations = [_destination_of(details) for _level, _title, _page, details in entries]
        if len(destinations) < 2 or None in destinations:
            return False
        return len({destination.y for destination in destinations}) == 1

    def _heading(self, document, entry: list) -> Heading:
        level, title, page, details = entry
        return Heading(int(level), outline_title(str(title)), int(page), self._position(document, int(page), details))

    def _position(self, document, page: int, details: dict) -> float:
        destination = _destination_of(details)
        if destination is None:
            return PAGE_TOP
        height = document[page - 1].rect.height
        depth = _depth_of(destination, details, height)
        if self._at_page_edge(depth) or self._at_page_edge(height - depth):
            return PAGE_TOP
        return depth

    @staticmethod
    def _at_page_edge(distance_from_edge: float) -> bool:
        return distance_from_edge <= DESTINATION_EDGE_TOLERANCE



def _depth_of(destination: pymupdf.Point, details: dict, height: float) -> float:
    return height - destination.y if details.get("kind") == pymupdf.LINK_NAMED else destination.y


def _destination_of(details: dict) -> pymupdf.Point | None:
    return details.get("to") if isinstance(details, dict) else None
