from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import FOOTNOTE_KIND, HEADING_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.elements import Heading, Paragraph
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.outline import Outline
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

FONT = "helv"
DISPLAY_SIZE = 14.0
BODY_SIZE = 10.0
NOTE_SIZE = 8.0
MARK_SIZE = 7.0
MARK_RISE = 7.0
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
FIRST_BASELINE = 80.0
LINE_PITCH = 40.0
LINE_HALF_HEIGHT = 12.0
SENTENCE = "The chapter opens with a sentence of its own."
NUMBER = "1"
TITLE = "Introduction to the Critique"
SUBTITLE = "Intuitive versus Discursive Understanding"
NUMBERED_TITLE = f"{NUMBER} {TITLE}: {SUBTITLE}"
PART_LABEL = "PART ONE"
PART_TITLE = "The Purpose of the Logic"
LABELLED_TITLE = f"{PART_LABEL} {PART_TITLE}"
CHAPTER_LABEL = "Chapter 1"
STAGE_TITLE = "Setting the Stage"
NUMBERED_STAGE_TITLE = f"{NUMBER} {STAGE_TITLE}"
ORDINAL_LABEL = "First Part"
PRINTED_PART_TITLE = "PROBLEM AND FORMS OF MEANING"
DASHED_TITLE = f"{ORDINAL_LABEL} — Problem and Forms of Meaning"
NOTE = "This chapter draws on an earlier paper."
NOTE_LABEL = "[^1]"


@dataclass(frozen=True)
class PrintedLine:
    text: str
    kind: str = HEADING_KIND
    size: float = DISPLAY_SIZE
    mark: str = ""

    def draw_on(self, page, baseline: float) -> None:
        page.insert_text((LEFT, baseline), self.text, fontsize=self.size, fontname=FONT)
        if self.mark:
            mark_left = LEFT + pymupdf.get_text_length(self.text, FONT, self.size)
            page.insert_text((mark_left, baseline - MARK_RISE), self.mark, fontsize=MARK_SIZE, fontname=FONT)

    @property
    def html(self) -> str:
        tag = "h1" if self.kind == HEADING_KIND else "p"
        mark = f"<sup>{self.mark}</sup>" if self.mark else ""
        return f"<{tag}>{self.text}{mark}</{tag}>"


class TitlePagePdf:
    def __init__(self, path: Path, lines: list[PrintedLine], outline_title: str) -> None:
        self._path = path
        self._lines = lines + [PrintedLine(SENTENCE, TEXT_KIND, BODY_SIZE),
                               PrintedLine(f"1 {NOTE}", FOOTNOTE_KIND, NOTE_SIZE)]
        self._outline_title = outline_title

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            for row, line in enumerate(self._lines):
                line.draw_on(page, _baseline(row))
            document.set_toc([[1, self._outline_title, 1]])
            document.save(self._path)
        return self._path

    @property
    def blocks(self) -> DocumentBlocks:
        return DocumentBlocks([PageBlocks(1, [_engine_block(row, line) for row, line in enumerate(self._lines)])])


def _baseline(row: int) -> float:
    return FIRST_BASELINE + row * LINE_PITCH


def _engine_block(row: int, line: PrintedLine) -> Block:
    baseline = _baseline(row)
    box = (LEFT, baseline - line.size - LINE_HALF_HEIGHT / 2, RIGHT, baseline + LINE_HALF_HEIGHT / 2)
    return Block(1, line.kind, line.html, box, {}, f"/page/1/{line.kind}/{row}")


class TestTitleBlocksPrintingThePartsOfACombinedOutlineTitle(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._directory = Path(directory.name)

    def _written(self, lines: list[PrintedLine], outline_title: str) -> list[str]:
        pdf = TitlePagePdf(self._directory / "title.pdf", lines, outline_title)
        pdf_path = pdf.write()
        layer = TextLayer(pdf_path)
        self.addCleanup(layer.close)
        inputs = StructureInputs(pdf.blocks, Outline(pdf_path).headings(), WorkerReadings.none(), keep_everything())
        elements = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs).elements()
        return [element.title if isinstance(element, Heading) else element.text for element in elements
                if isinstance(element, (Heading, Paragraph))]

    def test_a_number_title_and_subtitle_printed_apart_are_written_once_as_the_outline_title(self) -> None:
        lines = [PrintedLine(NUMBER), PrintedLine(TITLE), PrintedLine(SUBTITLE)]
        self.assertEqual([NUMBERED_TITLE, SENTENCE], self._written(lines, NUMBERED_TITLE))

    def test_a_label_the_engine_reads_as_text_above_the_title_is_written_once_as_the_outline_title(self) -> None:
        lines = [PrintedLine(PART_LABEL, TEXT_KIND), PrintedLine(PART_TITLE)]
        self.assertEqual([LABELLED_TITLE, SENTENCE], self._written(lines, LABELLED_TITLE))

    def test_a_label_and_title_the_outline_joins_with_a_dash_are_written_once_as_the_outline_title(self) -> None:
        lines = [PrintedLine(ORDINAL_LABEL, TEXT_KIND), PrintedLine(PRINTED_PART_TITLE)]
        self.assertEqual([DASHED_TITLE, SENTENCE], self._written(lines, DASHED_TITLE))

    def test_a_labelled_title_the_outline_numbers_without_its_label_is_written_once(self) -> None:
        lines = [PrintedLine(f"{CHAPTER_LABEL} {STAGE_TITLE}")]
        self.assertEqual([NUMBERED_STAGE_TITLE, SENTENCE], self._written(lines, NUMBERED_STAGE_TITLE))

    def test_a_bare_label_above_the_title_the_outline_numbers_is_written_once(self) -> None:
        lines = [PrintedLine(CHAPTER_LABEL), PrintedLine(STAGE_TITLE)]
        self.assertEqual([NUMBERED_STAGE_TITLE, SENTENCE], self._written(lines, NUMBERED_STAGE_TITLE))

    def test_a_note_mark_raised_on_a_part_printed_apart_stays_beside_the_outline_title(self) -> None:
        lines = [PrintedLine(NUMBER), PrintedLine(TITLE), PrintedLine(SUBTITLE, mark="1")]
        self.assertEqual([NUMBERED_TITLE, NOTE_LABEL, SENTENCE], self._written(lines, NUMBERED_TITLE))

    def test_a_subtitle_printed_under_a_title_the_outline_gives_alone_stays_a_heading(self) -> None:
        lines = [PrintedLine(TITLE), PrintedLine(SUBTITLE)]
        self.assertEqual([TITLE, SUBTITLE, SENTENCE], self._written(lines, TITLE))


if __name__ == "__main__":
    unittest.main()
