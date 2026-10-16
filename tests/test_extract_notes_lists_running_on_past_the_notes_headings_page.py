from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import FOOTNOTE_KIND, HEADING_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.outline import PAGE_TOP, Heading as OutlineHeading
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs
from _extract.writer import NoteWriter

FONT = "cour"
FONT_SIZE = 9.0
VISIBLE = 0
INVISIBLE = 3
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
FIRST_BASELINE = 100.0
LINE_PITCH = 20.0
LINE_HALF_HEIGHT = 8.0
INDENT = "    "
BODY = "The closing sentence of the body."
NOTES_TITLE = "NOTES"
FIRST_PAGE_BLOCKS = [(TEXT_KIND, [BODY]), (HEADING_KIND, [NOTES_TITLE]), (FOOTNOTE_KIND, ["1 The first endnote."]),
                     (FOOTNOTE_KIND, ["2 The second endnote."])]
SECOND_PAGE_BLOCKS = [(FOOTNOTE_KIND, ["3 The third endnote."]), (FOOTNOTE_KIND, ["4 The fourth endnote."])]
INDENTED_BODY_BLOCK = (TEXT_KIND, [f"{INDENT}A paragraph of the body opens on an indented", "line and runs on flush."])
APPENDIX_TITLE = "APPENDIX"
APPENDIX_BODY = "The appendix raises a mark.<sup>5</sup>"
APPENDIX_FOOTNOTE = "5 A footnote of the appendix."
APPENDIX_PAGE_BLOCKS = [(HEADING_KIND, [APPENDIX_TITLE]), (TEXT_KIND, [APPENDIX_BODY]),
                        (FOOTNOTE_KIND, [APPENDIX_FOOTNOTE])]
APPENDIX_WITH_A_NOTES_TEXT_BLOCK = APPENDIX_PAGE_BLOCKS + [(TEXT_KIND, ["Notes"])]
NOTES_ROW = 1
APPENDIX_OUTLINE = [OutlineHeading(1, NOTES_TITLE, 1, FIRST_BASELINE + NOTES_ROW * LINE_PITCH - LINE_HALF_HEIGHT),
                    OutlineHeading(1, APPENDIX_TITLE, 2, PAGE_TOP)]
EXPECTED_BODY = ["%% file p. 1 %%", BODY, f"# {NOTES_TITLE}", "1 The first endnote.", "2 The second endnote.",
                 "%% file p. 2 %%", "3 The third endnote.", "4 The fourth endnote."]
EXPECTED_SCAN_NOTES = ["1 The first endnote.", "2 The second endnote.", "%% file p. 2 %%", "3 The third endnote.",
                       "4 The fourth endnote."]
PIXEL_PAGES = frozenset({1, 2})


@dataclass(frozen=True)
class NotesWork:
    pages: list[list[tuple[str, list[str]]]]
    outline: list[OutlineHeading] = field(default_factory=list)
    pixel_pages: frozenset[int] = frozenset()


def rows_of(blocks: list[tuple[str, list[str]]]) -> list[str]:
    return [line for _kind, lines in blocks for line in lines]


def baseline_of(row: int) -> float:
    return FIRST_BASELINE + row * LINE_PITCH


class NotesOverTwoPagesPdf:
    def __init__(self, path: Path, work: NotesWork) -> None:
        self._path = path
        self._work = work
        self._render_mode = VISIBLE

    def write(self) -> Path:
        with pymupdf.open() as document:
            for file_page, blocks in enumerate(self._work.pages, start=1):
                page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
                self._render_mode = INVISIBLE if file_page in self._work.pixel_pages else VISIBLE
                for row, line in enumerate(rows_of(blocks)):
                    self._line(page, row, line)
            document.save(self._path)
        return self._path

    def _line(self, page, row: int, line: str) -> None:
        text = line.replace("<sup>", "").replace("</sup>", "")
        left = LEFT + pymupdf.get_text_length(text[:len(text) - len(text.lstrip())], FONT, FONT_SIZE)
        page.insert_text((left, baseline_of(row)), text.lstrip(), fontsize=FONT_SIZE, fontname=FONT,
                         render_mode=self._render_mode)


def engine_reading(pages: list[list[tuple[str, list[str]]]]) -> list[PageBlocks]:
    return [PageBlocks(file_page, engine_blocks(file_page, blocks)) for file_page, blocks in enumerate(pages, start=1)]


def engine_blocks(file_page: int, blocks: list[tuple[str, list[str]]]) -> list[Block]:
    read, row = [], 0
    for kind, lines in blocks:
        box = (LEFT, baseline_of(row) - LINE_HALF_HEIGHT, RIGHT,
               baseline_of(row + len(lines) - 1) + LINE_HALF_HEIGHT / 2)
        html = f"<p>{' '.join(line.strip() for line in lines)}</p>"
        read.append(Block(file_page, kind, html, box, {}, f"/page/{file_page}/{kind}/{row}"))
        row += len(lines)
    return read


def written(work: NotesWork) -> tuple[str, list]:
    with tempfile.TemporaryDirectory() as directory:
        layer = TextLayer(NotesOverTwoPagesPdf(Path(directory) / "notes.pdf", work).write())
        try:
            inputs = StructureInputs(DocumentBlocks(engine_reading(work.pages)), work.outline, WorkerReadings.none(),
                                     keep_everything())
            work_inputs = WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts(), pixel_pages=work.pixel_pages)
            structure = NoteStructure(work_inputs, inputs)
            text = NoteWriter().render(structure.elements(), structure.definitions()).text
            return text, structure.definitions()
        finally:
            layer.close()


class TestNotesListsRunningOnPastTheNotesHeadingsPage(unittest.TestCase):
    def test_the_entries_the_engine_reads_as_footnotes_on_the_next_page_stay_in_the_notes_list(self) -> None:
        text, _definitions = written(NotesWork([FIRST_PAGE_BLOCKS, SECOND_PAGE_BLOCKS]))
        self.assertEqual(EXPECTED_BODY, text.strip().split("\n\n"))

    def test_the_entries_opening_the_next_page_of_a_scan_stay_entries_of_their_own_after_its_page_marker(
            self) -> None:
        pages = [[INDENTED_BODY_BLOCK] + FIRST_PAGE_BLOCKS, SECOND_PAGE_BLOCKS]
        text, _definitions = written(NotesWork(pages, pixel_pages=PIXEL_PAGES))
        self.assertEqual(EXPECTED_SCAN_NOTES, text.strip().split("\n\n")[-5:])

    def test_the_footnotes_of_a_page_opening_a_section_of_its_own_after_the_notes_list_stay_footnotes(self) -> None:
        _text, definitions = written(NotesWork([FIRST_PAGE_BLOCKS, APPENDIX_PAGE_BLOCKS]))
        self.assertEqual(["5"], [definition.number for definition in definitions])

    def test_the_footnotes_of_a_page_opening_a_section_beside_a_notes_heading_set_as_text_stay_footnotes(
            self) -> None:
        _text, definitions = written(NotesWork([FIRST_PAGE_BLOCKS, APPENDIX_WITH_A_NOTES_TEXT_BLOCK]))
        self.assertEqual(["5"], [definition.number for definition in definitions])

    def test_the_footnotes_of_a_page_an_outline_entry_opens_after_the_notes_list_stay_footnotes(self) -> None:
        _text, definitions = written(NotesWork([FIRST_PAGE_BLOCKS, APPENDIX_PAGE_BLOCKS[1:]], APPENDIX_OUTLINE))
        self.assertEqual(["5"], [definition.number for definition in definitions])


if __name__ == "__main__":
    unittest.main()
