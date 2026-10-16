from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs
from _extract.writer import NoteWriter

FONT = "cour"
FONT_SIZE = 9.0
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
FIRST_BASELINE = 100.0
LINE_PITCH = 20.0
LINE_HALF_HEIGHT = 8.0
NOTES_TITLE = "NOTES"
FIRST_PAGE_LINES = [NOTES_TITLE, "1 The first endnote.", "2 The second endnote opens on the first page and"]
SECOND_PAGE_LINES = ["Runs On to the second page.", "3 The third endnote.", "4 The fourth endnote."]
CARRIED_ENTRY = "2 The second endnote opens on the first page and %% file p. 2 %% Runs On to the second page."
ENDING_ENTRY = "2 The second endnote closes on the first page."
PARAGRAPH_OPENING_THE_PAGE = "A second paragraph of the second endnote opens the next page."


class NotesOverTwoPagesPdf:
    def __init__(self, path: Path, pages: list[list[str]]) -> None:
        self._path = path
        self._pages = pages

    def write(self) -> Path:
        with pymupdf.open() as document:
            for lines in self._pages:
                page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
                for row, line in enumerate(lines):
                    page.insert_text((LEFT, baseline_of(row)), line, fontsize=FONT_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


def baseline_of(row: int) -> float:
    return FIRST_BASELINE + row * LINE_PITCH


@dataclass(frozen=True)
class PageRow:
    file_page: int
    row: int


def engine_block(kind: str, text: str, place: PageRow) -> Block:
    baseline = baseline_of(place.row)
    box = (LEFT, baseline - LINE_HALF_HEIGHT, RIGHT, baseline + LINE_HALF_HEIGHT / 2)
    return Block(place.file_page, kind, f"<p>{text}</p>", box, {}, f"/page/{place.file_page}/{kind}/{place.row}")


def engine_reading(pages: list[list[str]]) -> list[PageBlocks]:
    return [PageBlocks(file_page, [engine_block(HEADING_KIND if line == NOTES_TITLE else TEXT_KIND, line,
                                                PageRow(file_page, row))
                                   for row, line in enumerate(lines)])
            for file_page, lines in enumerate(pages, start=1)]


def written_paragraphs(pages: list[list[str]]) -> list[str]:
    with tempfile.TemporaryDirectory() as directory:
        layer = TextLayer(NotesOverTwoPagesPdf(Path(directory) / "notes.pdf", pages).write())
        try:
            work = WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts())
            inputs = StructureInputs(DocumentBlocks(engine_reading(pages)), [], WorkerReadings.none(),
                                     keep_everything())
            structure = NoteStructure(work, inputs)
            text = NoteWriter().render(structure.elements(), structure.definitions()).text
        finally:
            layer.close()
    return text.strip().split("\n\n")


class TestNumberedEntriesRunningOverAPageBreak(unittest.TestCase):
    def setUp(self) -> None:
        self.paragraphs = written_paragraphs([FIRST_PAGE_LINES, SECOND_PAGE_LINES])

    def test_an_entry_a_numbered_list_carries_over_a_page_break_stays_one_entry(self) -> None:
        self.assertIn(CARRIED_ENTRY, self.paragraphs)

    def test_the_entries_after_the_carried_entry_open_on_their_numbers(self) -> None:
        self.assertEqual(["3 The third endnote.", "4 The fourth endnote."], self.paragraphs[-2:])


class TestNumberedEntriesEndingASentenceAtAPageBreak(unittest.TestCase):
    def test_an_unnumbered_paragraph_opening_the_page_after_an_entry_ending_a_sentence_stays_its_own(self) -> None:
        pages = [FIRST_PAGE_LINES[:-1] + [ENDING_ENTRY], [PARAGRAPH_OPENING_THE_PAGE] + SECOND_PAGE_LINES[1:]]
        paragraphs = written_paragraphs(pages)
        self.assertEqual([ENDING_ENTRY, "%% file p. 2 %%", PARAGRAPH_OPENING_THE_PAGE], paragraphs[-5:-2])


if __name__ == "__main__":
    unittest.main()
