from __future__ import annotations

from dataclasses import dataclass

from page_marker import PageMarker

LIST_ITEM_BULLET = "- "


@dataclass(frozen=True)
class Heading:
    level: int
    title: str
    file_page: int
    key: tuple | None = None

    def at_level(self, level: int) -> "Heading":
        return Heading(level, self.title, self.file_page, None)


@dataclass(frozen=True)
class Paragraph:
    text: str
    continues: bool
    file_page: int
    resumes: bool = False
    resumes_mid_sentence: bool = False
    is_caption: bool = False


@dataclass(frozen=True)
class Verbatim:
    text: str
    file_page: int


__all__ = ["LIST_ITEM_BULLET", "Heading", "PageMarker", "Paragraph", "Verbatim"]
