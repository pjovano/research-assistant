from __future__ import annotations

import shutil
import tempfile
import unittest
from dataclasses import dataclass
from itertools import cycle, islice
from pathlib import Path

import pymupdf

PORTRAIT = (612, 792)
SPREAD = (1224, 792)
LEFT_MARGIN = 72
BODY_BASELINE = 90
BODY_SIZE = 11
BODY_PITCH = 17
SMALL_SIZE = 8
SMALL_PITCH = 11
HEAD_BASELINE = 50
NOTES_GAP = 30
FONT = "helv"
WORDS_PER_LINE = 10
BODY_LINES = 24
PAGE_WORDS = WORDS_PER_LINE * BODY_LINES
FILLER = ("river", "stone", "garden", "window", "harbor", "lantern",
          "meadow", "orchard", "thunder", "copper", "valley", "forest", "bridge")
BOOK_NAME = "book.pdf"


class ProseLines:
    def __init__(self, seed: int, line_count: int = BODY_LINES) -> None:
        self._seed = seed
        self._line_count = line_count

    def placing(self, placed: dict[int, str] | None = None) -> tuple[tuple[str, ...], ...]:
        words = self._filler()
        for index, word in (placed or {}).items():
            words[index] = word
        return tuple(tuple(words[start:start + WORDS_PER_LINE])
                     for start in range(0, len(words), WORDS_PER_LINE))

    def _filler(self) -> list[str]:
        count = self._line_count * WORDS_PER_LINE
        return list(islice(cycle(FILLER), self._seed, self._seed + count))


@dataclass(frozen=True)
class BookPage:
    lines: tuple[tuple[str, ...], ...]
    right_lines: tuple[tuple[str, ...], ...] = ()
    notes: tuple[tuple[str, ...], ...] = ()
    head: str = ""

    @property
    def size(self) -> tuple[int, int]:
        return SPREAD if self.right_lines else PORTRAIT


class PageWriter:
    def __init__(self, page, content: BookPage) -> None:
        self._page = page
        self._content = content

    def write(self) -> None:
        self._write_lines(self._content.lines, LEFT_MARGIN)
        self._write_lines(self._content.right_lines, self._page.rect.width / 2 + LEFT_MARGIN)
        self._write_notes()
        self._write_head()

    def _write_lines(self, lines, left: float) -> None:
        for number, words in enumerate(lines):
            self._insert((left, BODY_BASELINE + number * BODY_PITCH), " ".join(words), BODY_SIZE)

    def _write_notes(self) -> None:
        first_baseline = BODY_BASELINE + len(self._content.lines) * BODY_PITCH + NOTES_GAP
        for number, words in enumerate(self._content.notes):
            self._insert((LEFT_MARGIN, first_baseline + number * SMALL_PITCH), " ".join(words), SMALL_SIZE)

    def _write_head(self) -> None:
        if self._content.head:
            self._insert((LEFT_MARGIN, HEAD_BASELINE), self._content.head, SMALL_SIZE)

    def _insert(self, origin: tuple[float, float], text: str, size: int) -> None:
        self._page.insert_text(origin, text, fontsize=size, fontname=FONT)


@dataclass(frozen=True)
class PageLabelRun:
    first_page: int
    style: str
    first_number: int = 1

    def as_rule(self) -> dict:
        return {"startpage": self.first_page, "prefix": "", "style": self.style, "firstpagenum": self.first_number}


class BookPdf:
    def __init__(self, pages: list[BookPage], outline: list | None = None,
                 label_runs: tuple[PageLabelRun, ...] = ()) -> None:
        self._pages = pages
        self._outline = outline or []
        self._label_runs = label_runs

    def write(self, path: Path) -> Path:
        with pymupdf.open() as document:
            for content in self._pages:
                width, height = content.size
                PageWriter(document.new_page(width=width, height=height), content).write()
            document.set_toc(self._outline)
            self._label(document)
            document.save(path)
        return path

    def _label(self, document) -> None:
        if self._label_runs:
            document.set_page_labels([run.as_rule() for run in self._label_runs])


class BuiltPdfTestCase(unittest.TestCase):
    BOOK: BookPdf

    @classmethod
    def setUpClass(cls) -> None:
        cls.built_directory = Path(tempfile.mkdtemp())
        cls.pdf = cls.BOOK.write(cls.built_directory / BOOK_NAME)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.built_directory, ignore_errors=True)
