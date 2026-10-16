from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _book_fixtures import BOOK_NAME, PAGE_WORDS, BookPage, BookPdf, BuiltPdfTestCase, ProseLines
import annotate

MARKED_PAGE = 1
LEADING_PAGE = 2
TRAILING_PAGE = 3
TRAILING_MARKER = (56, "composed.[A", "170]")
ENDING_MARKER = (PAGE_WORDS - 2, "cognition.[B", "15]")
BREAK_START = PAGE_WORDS - 14
BREAK_WORDS = {BREAK_START: "But", BREAK_START + 1: "since",
               PAGE_WORDS - 2: "empirical,", PAGE_WORDS - 1: "we"}
CONTINUED_WORDS = {0: "cannot", 1: "anticipate", 18: "system.[A", 19: "172]"}
BREAK_END = 20
WRITING_OUTLINE = [[1, "First chapter", MARKED_PAGE], [1, "Second chapter", LEADING_PAGE]]


@dataclass(frozen=True)
class WordSpan:
    page: int
    start: int
    end: int


class WritingBook:
    @staticmethod
    def pdf() -> BookPdf:
        return BookPdf([BookPage(ProseLines(0).placing(WritingBook._marked())),
                        BookPage(ProseLines(3).placing(BREAK_WORDS)),
                        BookPage(ProseLines(7).placing(CONTINUED_WORDS))], WRITING_OUTLINE)

    @staticmethod
    def _marked() -> dict[int, str]:
        placed = {}
        for index, opener, closer in (TRAILING_MARKER, ENDING_MARKER):
            placed[index], placed[index + 1] = opener, closer
        return placed


class WritableCopyTestCase(BuiltPdfTestCase):
    BOOK = WritingBook.pdf()

    def setUp(self) -> None:
        self.directory = Path(tempfile.mkdtemp())
        self.copy = self.directory / BOOK_NAME
        shutil.copy(self.pdf, self.copy)

    def tearDown(self) -> None:
        shutil.rmtree(self.directory, ignore_errors=True)

    def highlight(self, span: WordSpan, link: str) -> annotate.AnnotationRequest:
        return annotate.AnnotationRequest(span.page, span.start, span.end, annotate.Note(link, "a gloss"))

    def write(self, requests) -> None:
        annotate.AnnotationWriter(self.copy, "Tester").apply(requests)
