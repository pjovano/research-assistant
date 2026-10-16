from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import FOOTER_KIND, FOOTNOTE_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

FONT = "helv"
BODY_SIZE = 10.0
NOTE_SIZE = 8.0
MARK_SIZE = 6.0
MARK_RISE = 4.0
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
LINE_HALF_HEIGHT = 8.0
BODY_BASELINE = 100.0
FIRST_NOTE_BASELINE = 560.0
SECOND_NOTE_BASELINE = 572.0
FIRST_SENTENCE = "The argument is valid, but it proves too much."
SECOND_SENTENCE = "A second paragraph opens the following page."
NOTE_OPENING = "For the classic statement, see the essay in its first edition, New York: Columbia University"
NOTE_CONTINUATION = "Press, 1969, pp. 69-90."
SECOND_NOTE = "The same author, the second work, p. 246."
JOURNAL_FOOTER = "Journal of the History of Tests"


@dataclass(frozen=True)
class NotedPage:
    sentence: str
    mark: str
    note_lines: tuple[str, ...]

    def draw_on(self, page) -> None:
        page.insert_text((LEFT, BODY_BASELINE), self.sentence, fontsize=BODY_SIZE, fontname=FONT)
        mark_left = LEFT + pymupdf.get_text_length(self.sentence, FONT, BODY_SIZE)
        page.insert_text((mark_left, BODY_BASELINE - MARK_RISE), self.mark, fontsize=MARK_SIZE, fontname=FONT)
        for baseline, text in zip((FIRST_NOTE_BASELINE, SECOND_NOTE_BASELINE), self.note_lines):
            page.insert_text((LEFT, baseline), text, fontsize=NOTE_SIZE, fontname=FONT)


class NotedPdf:
    def __init__(self, path: Path, pages: list[NotedPage]) -> None:
        self._path = path
        self._pages = pages

    def write(self) -> Path:
        with pymupdf.open() as document:
            for noted in self._pages:
                noted.draw_on(document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT))
            document.save(self._path)
        return self._path


@dataclass(frozen=True)
class EngineRegion:
    top_baseline: float
    bottom_baseline: float

    def block(self, file_page: int, kind: str, html: str) -> Block:
        box = (LEFT, self.top_baseline - LINE_HALF_HEIGHT, RIGHT, self.bottom_baseline + LINE_HALF_HEIGHT / 2)
        return Block(file_page, kind, html, box, {}, f"/page/{file_page}/{kind}/{self.top_baseline}")


BODY_REGION = EngineRegion(BODY_BASELINE, BODY_BASELINE)
NOTES_REGION = EngineRegion(FIRST_NOTE_BASELINE, SECOND_NOTE_BASELINE)


def body_block(file_page: int, sentence: str, mark: str) -> Block:
    return BODY_REGION.block(file_page, TEXT_KIND, f"<p>{sentence}{mark}</p>")


def notes_block(file_page: int, kind: str, text: str) -> Block:
    return NOTES_REGION.block(file_page, kind, f"<p>{text}</p>")


class FooterCase(unittest.TestCase):
    def built(self, pages: list[NotedPage], engine_pages: list[PageBlocks]) -> NoteStructure:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(NotedPdf(Path(directory.name) / "notes.pdf", pages).write())
        self.addCleanup(layer.close)
        blocks = DocumentBlocks(engine_pages)
        inputs = StructureInputs(blocks, [], WorkerReadings.none(), keep_everything())
        work = WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts(), furniture=blocks.furniture_texts)
        return NoteStructure(work, inputs)


class TestFootnotesTheEngineReadsAsAPageFooter(FooterCase):
    def setUp(self) -> None:
        pages = [NotedPage(FIRST_SENTENCE, "1", (f"1 {NOTE_OPENING}",)),
                 NotedPage(SECOND_SENTENCE, "2", (NOTE_CONTINUATION, f"2 {SECOND_NOTE}"))]
        engine_pages = [
            PageBlocks(1, [body_block(1, FIRST_SENTENCE, "1"),
                           notes_block(1, FOOTNOTE_KIND, f"<sup>1 </sup>{NOTE_OPENING}")]),
            PageBlocks(2, [body_block(2, SECOND_SENTENCE, "2"),
                           notes_block(2, FOOTER_KIND, f"{NOTE_CONTINUATION} 2 {SECOND_NOTE}")]),
        ]
        self.structure = self.built(pages, engine_pages)

    def test_the_footers_opening_line_continues_the_note_begun_on_the_page_before(self) -> None:
        self.assertEqual(f"{NOTE_OPENING} {NOTE_CONTINUATION}", self.structure.definitions()[0].text)

    def test_the_footers_numbered_note_pairs_with_its_mark(self) -> None:
        self.assertEqual(SECOND_NOTE, self.structure.definitions()[1].text)

    def test_no_mark_is_left_without_its_note(self) -> None:
        self.assertEqual([], self.structure.footnote_log())


class TestARunningFooterOpeningWithAMarkedNumber(FooterCase):
    def setUp(self) -> None:
        pages = [NotedPage(FIRST_SENTENCE, "1", (f"1 {JOURNAL_FOOTER}",)),
                 NotedPage(SECOND_SENTENCE, "2", (f"2 {JOURNAL_FOOTER}",))]
        engine_pages = [PageBlocks(page, [body_block(page, sentence, str(page)),
                                          notes_block(page, FOOTER_KIND, f"{page} {JOURNAL_FOOTER}")])
                        for page, sentence in ((1, FIRST_SENTENCE), (2, SECOND_SENTENCE))]
        self.structure = self.built(pages, engine_pages)

    def test_a_footer_the_work_repeats_stays_out_of_the_notes(self) -> None:
        self.assertEqual([], self.structure.definitions())


if __name__ == "__main__":
    unittest.main()
