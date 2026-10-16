from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import FURNITURE_KINDS, HEADING_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.elements import Heading, Paragraph, Verbatim
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

HEADER_KIND = FURNITURE_KINDS[0]
FONT_SIZE = 10.0
LINE_PITCH = 14.0
HALF_LINE = 7.0
DESCENT = 3.0
MEASURE_LEFT = 72.0
MEASURE_RIGHT = 520.0
RIGHT_COLUMN_LEFT = 300.0
COLUMN_WIDTH = 200.0
PARAGRAPHS_PER_PAGE = 4
FIRST_BASELINE = 80.0
OPENING = ("The two lists below set the expressions of each group side by side, so that each row pairs",
           "an expression of the first group with the one that contradicts it in the second group here.")
CLOSING = ("These pairs show that the contradictory of each expression follows from the expressions",
           "of the other group, and that the negation of each follows from the affirmation over it.")
LABELS = ("I", "II")
PAIRED_ROWS = (("possible to be", "not possible to be"), ("admissible to be", "not admissible to be"),
               ("not impossible to be", "impossible to be"))
CAPTIONS = ("On Clarity", "Critique")
LEFT_PROSE = ("Every general concept can be reached", "by two ways, either by the arbitrary",
              "combination of concepts or by an", "abstraction from a cognition made clear.")
CLOSING_LINE = "Hence every case of the claim holds."
CLOSING_MARK = "end"
NEXT_HEADING = "2. The next section"
SKIPPED_ROWS = 5
FIGURE_CAPTION = ("Figure 1", "Values on the naive theory.")
RIGHT_PROSE = ("Philosophical definitions are only", "expositions of given concepts.")


@dataclass(frozen=True)
class _Line:
    left: float
    text: str


class _PageDrawing:
    def __init__(self, page) -> None:
        self._page = page
        self._baseline = FIRST_BASELINE

    def paragraph(self, lines: tuple[str, ...]) -> tuple[float, float, float, float]:
        top = self.top
        for text in lines:
            self.row([_Line(MEASURE_LEFT, text)])
        return (MEASURE_LEFT, top, MEASURE_RIGHT, self._baseline - LINE_PITCH + DESCENT)

    def row(self, lines: list[_Line]) -> None:
        for line in lines:
            self._page.insert_text((line.left, self._baseline), line.text, fontsize=FONT_SIZE, fontname="helv")
        self._baseline += LINE_PITCH

    @property
    def top(self) -> float:
        return self._baseline - FONT_SIZE


def _column_box(left: float, top: float, rows: int) -> tuple[float, float, float, float]:
    return (left, top, left + COLUMN_WIDTH, top + (rows - 1) * LINE_PITCH + FONT_SIZE + DESCENT)


@dataclass
class _BuiltPage:
    file_page: int
    blocks: list[Block]

    def add(self, kind: str, box: tuple[float, float, float, float], html: str) -> None:
        identifier = f"/page/{self.file_page}/{kind}/{len(self.blocks)}"
        self.blocks.append(Block(self.file_page, kind, html, box, {}, identifier))

    def paragraphs(self, drawing: _PageDrawing, count: int) -> None:
        for _ in range(count):
            self.add(TEXT_KIND, drawing.paragraph(OPENING), " ".join(OPENING))

    def prose_columns(self, drawing: _PageDrawing) -> None:
        prose_top = drawing.top
        for position, left_line in enumerate(LEFT_PROSE):
            right = [_Line(RIGHT_COLUMN_LEFT, RIGHT_PROSE[position])] if position < len(RIGHT_PROSE) else []
            drawing.row([_Line(MEASURE_LEFT, left_line)] + right)
        self.add(TEXT_KIND, _column_box(MEASURE_LEFT, prose_top, len(LEFT_PROSE)), " ".join(LEFT_PROSE))
        self.add(TEXT_KIND, _column_box(RIGHT_COLUMN_LEFT, prose_top, len(RIGHT_PROSE)), " ".join(RIGHT_PROSE))

    @property
    def page(self) -> PageBlocks:
        return PageBlocks(self.file_page, self.blocks)


class _Work:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._document = pymupdf.open()
        self._pages: list[PageBlocks] = []

    def page(self) -> tuple[_BuiltPage, _PageDrawing]:
        return _BuiltPage(len(self._pages) + 1, []), _PageDrawing(self._document.new_page())

    def add(self, built: _BuiltPage) -> None:
        self._pages.append(built.page)

    def saved(self) -> DocumentBlocks:
        self._document.save(self._path)
        self._document.close()
        return DocumentBlocks(self._pages)


def _one_column_work(path: Path) -> _Work:
    work = _Work(path)
    built, drawing = work.page()
    built.paragraphs(drawing, PARAGRAPHS_PER_PAGE)
    work.add(built)
    return work


def _paired_lists_page(path: Path) -> DocumentBlocks:
    work = _one_column_work(path)
    built, drawing = work.page()
    built.paragraphs(drawing, 1)
    labels_top = drawing.top
    drawing.row([_Line(MEASURE_LEFT, LABELS[0]), _Line(RIGHT_COLUMN_LEFT, LABELS[1])])
    built.add(TEXT_KIND, _column_box(MEASURE_LEFT, labels_top, 1)[:2] + (RIGHT_COLUMN_LEFT + HALF_LINE, drawing.top),
              " ".join(LABELS))
    rows_top = drawing.top
    for left, right in PAIRED_ROWS:
        drawing.row([_Line(MEASURE_LEFT, left), _Line(RIGHT_COLUMN_LEFT, right)])
    for column, left in enumerate((MEASURE_LEFT, RIGHT_COLUMN_LEFT)):
        built.add(TEXT_KIND, _column_box(left, rows_top, len(PAIRED_ROWS)),
                  " ".join(pair[column] for pair in PAIRED_ROWS))
    built.add(TEXT_KIND, drawing.paragraph(CLOSING), " ".join(CLOSING))
    work.add(built)
    return work.saved()


def _captioned_prose_page(path: Path, caption_kind: str) -> DocumentBlocks:
    work = _one_column_work(path)
    built, drawing = work.page()
    built.paragraphs(drawing, 1)
    captions_top = drawing.top
    drawing.row([_Line(MEASURE_LEFT, CAPTIONS[0]), _Line(RIGHT_COLUMN_LEFT, CAPTIONS[1])])
    closing = _BuiltPage(built.file_page, [])
    closing.prose_columns(drawing)
    built.add(TEXT_KIND, drawing.paragraph(CLOSING), " ".join(CLOSING))
    for left, caption in zip((MEASURE_LEFT, RIGHT_COLUMN_LEFT), CAPTIONS):
        built.add(caption_kind, _column_box(left, captions_top, 1), caption)
    built.blocks.extend(closing.blocks)
    work.add(built)
    return work.saved()


def _closing_mark_page(path: Path) -> DocumentBlocks:
    work = _one_column_work(path)
    built, drawing = work.page()
    built.paragraphs(drawing, 1)
    mark_top = drawing.top
    drawing.row([_Line(MEASURE_LEFT, CLOSING_LINE), _Line(RIGHT_COLUMN_LEFT, CLOSING_MARK)])
    built.add(TEXT_KIND, _column_box(MEASURE_LEFT, mark_top, 1), CLOSING_LINE)
    built.add(TEXT_KIND, _column_box(RIGHT_COLUMN_LEFT, mark_top, 1), CLOSING_MARK)
    built.add(TEXT_KIND, drawing.paragraph(CLOSING), " ".join(CLOSING))
    work.add(built)
    return work.saved()


def _heading_below_columns_page(path: Path) -> DocumentBlocks:
    work = _one_column_work(path)
    built, drawing = work.page()
    built.paragraphs(drawing, 1)
    captions_top = drawing.top
    drawing.row([_Line(MEASURE_LEFT, CAPTIONS[0]), _Line(RIGHT_COLUMN_LEFT, CAPTIONS[1])])
    for left, caption in zip((MEASURE_LEFT, RIGHT_COLUMN_LEFT), CAPTIONS):
        built.add(HEADING_KIND, _column_box(left, captions_top, 1), caption)
    built.prose_columns(drawing)
    heading_top = drawing.top
    drawing.row([_Line(MEASURE_LEFT, NEXT_HEADING)])
    built.add(HEADING_KIND, _column_box(MEASURE_LEFT, heading_top, 1), NEXT_HEADING)
    built.add(TEXT_KIND, drawing.paragraph(CLOSING), " ".join(CLOSING))
    work.add(built)
    return work.saved()


def _gapped_column_page(path: Path) -> DocumentBlocks:
    work = _one_column_work(path)
    built, drawing = work.page()
    built.paragraphs(drawing, 1)
    rows_top = drawing.top
    drawing.row([_Line(MEASURE_LEFT, LABELS[0]), _Line(RIGHT_COLUMN_LEFT, RIGHT_PROSE[0])])
    drawing.row([_Line(RIGHT_COLUMN_LEFT, RIGHT_PROSE[1])])
    built.add(TEXT_KIND, _column_box(MEASURE_LEFT, rows_top, 1), LABELS[0])
    built.add(TEXT_KIND, _column_box(RIGHT_COLUMN_LEFT, rows_top, len(RIGHT_PROSE)), " ".join(RIGHT_PROSE))
    for _ in range(SKIPPED_ROWS):
        drawing.row([])
    caption_top = drawing.top
    for line in FIGURE_CAPTION:
        drawing.row([_Line(MEASURE_LEFT, line)])
    built.add(TEXT_KIND, _column_box(MEASURE_LEFT, caption_top, len(FIGURE_CAPTION)), " ".join(FIGURE_CAPTION))
    built.add(TEXT_KIND, drawing.paragraph(CLOSING), " ".join(CLOSING))
    work.add(built)
    return work.saved()


def _two_column_work_page(path: Path) -> DocumentBlocks:
    work = _Work(path)
    built, drawing = work.page()
    for _ in range(PARAGRAPHS_PER_PAGE):
        built.prose_columns(drawing)
    built.add(TEXT_KIND, drawing.paragraph(CLOSING), " ".join(CLOSING))
    work.add(built)
    return work.saved()


class _Written:
    def __init__(self, test: unittest.TestCase, path: Path, blocks: DocumentBlocks) -> None:
        layer = TextLayer(path)
        test.addCleanup(layer.close)
        inputs = StructureInputs(blocks, [], WorkerReadings.none(), keep_everything())
        elements = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs).elements()
        last_page = blocks.pages[-1].file_page
        self.elements = [element for element in elements if isinstance(element, (Heading, Paragraph, Verbatim))
                         and element.file_page == last_page]

    def table_lines(self) -> list[str]:
        tables = [element.text for element in self.elements if isinstance(element, Verbatim)]
        return tables[0].splitlines() if tables else []


class TestSideBySideColumnsSetBetweenTheTextOfAOneColumnWork(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._directory = Path(directory.name)

    def _written(self, build, *arguments) -> _Written:
        path = self._directory / "page.pdf"
        return _Written(self, path, build(path, *arguments))

    def test_lines_sharing_a_baseline_across_the_columns_fill_one_row(self) -> None:
        lines = self._written(_paired_lists_page).table_lines()
        self.assertEqual("| admissible to be | not admissible to be |", lines[3])

    def test_the_labels_over_the_columns_head_the_table(self) -> None:
        self.assertEqual("| I | II |", self._written(_paired_lists_page).table_lines()[0])

    def test_the_columns_stand_between_the_text_above_and_below_them(self) -> None:
        kinds = [type(element) for element in self._written(_paired_lists_page).elements]
        self.assertEqual([Paragraph, Verbatim, Paragraph], kinds)

    def test_captions_over_prose_columns_head_the_table(self) -> None:
        lines = self._written(_captioned_prose_page, HEADING_KIND).table_lines()
        self.assertEqual(f"| {CAPTIONS[0]} | {CAPTIONS[1]} |", lines[0])

    def test_captions_over_prose_columns_open_no_heading(self) -> None:
        elements = self._written(_captioned_prose_page, HEADING_KIND).elements
        self.assertFalse(any(isinstance(element, Heading) for element in elements))

    def test_captions_the_engine_reads_as_page_headers_head_the_table(self) -> None:
        lines = self._written(_captioned_prose_page, HEADER_KIND).table_lines()
        self.assertEqual(f"| {CAPTIONS[0]} | {CAPTIONS[1]} |", lines[0])

    def test_each_prose_column_flows_into_one_cell(self) -> None:
        lines = self._written(_captioned_prose_page, HEADING_KIND).table_lines()
        self.assertEqual(f"| {' '.join(LEFT_PROSE)} | {' '.join(RIGHT_PROSE)} |", lines[2])

    def test_a_column_the_engine_lists_after_the_text_below_it_is_written_above_that_text(self) -> None:
        kinds = [type(element) for element in self._written(_captioned_prose_page, HEADING_KIND).elements]
        self.assertEqual([Paragraph, Verbatim, Paragraph], kinds)

    def test_a_mark_set_beside_a_single_line_stays_prose(self) -> None:
        self.assertEqual([], self._written(_closing_mark_page).table_lines())

    def test_a_heading_below_the_columns_stays_a_heading(self) -> None:
        elements = self._written(_heading_below_columns_page).elements
        self.assertIn(NEXT_HEADING, [element.title for element in elements if isinstance(element, Heading)])

    def test_a_heading_below_the_columns_leaves_the_captions_heading_the_table(self) -> None:
        lines = self._written(_heading_below_columns_page).table_lines()
        self.assertEqual(f"| {CAPTIONS[0]} | {CAPTIONS[1]} |", lines[0])

    def test_a_column_broken_by_a_gap_of_several_lines_stays_prose(self) -> None:
        self.assertEqual([], self._written(_gapped_column_page).table_lines())

    def test_the_columns_of_a_work_set_in_two_columns_stay_prose(self) -> None:
        self.assertEqual([], self._written(_two_column_work_page).table_lines())


if __name__ == "__main__":
    unittest.main()
