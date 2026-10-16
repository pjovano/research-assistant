from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import HEADING_KIND, LIST_ITEM_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs
from _extract.writer import NoteWriter

HEADING_FONT = "helv"
EVEN_FONT = "cour"
FILE_PAGE = 1
PAGE_WIDTH, PAGE_HEIGHT = 432.0, 648.0
LEFT = 54.0
HANGING_INDENT = 30.0
PARAGRAPH_INDENT = 18.0
RIGHT = 400.0
BODY_SIZE = 9.0
HEADING_SIZE = 16.0
LINE_PITCH = 12.0
HEADING_BASELINE = 60.0
FIRST_ROW_BASELINE = 100.0
HEADING_TITLE = "Abbreviations"
RUN_IN_ENTRIES = (("PG Phenomenology of Spirit, translated by A. V. Miller", "(Oxford University Press, 1977)."),
                  ("PM Philosophy of Mind, translated by William Wallace", "(Clarendon Press, 1971)."),
                  ("SL Science of Logic, translated by A. V. Miller (Oxford", "University Press, 1989)."))
PROOF_STEPS = (("Suppose A.", 0), ("Hence C.", 1), ("Hence B.", 1), ("On the other hand, suppose not A.", 0),
               ("Hence D.", 1), ("Hence B.", 1), ("Hence B.", 0))
FULL_LINE = "word " * 9 + "word"
INDENTED_LINE = "word " * 6 + "word"
PARAGRAPHS = 2
RAGGED_LINES = (FULL_LINE, "word " * 7 + "word", "word " * 8 + "word")
CLOSING_LINE = "word word."
NOTE_MARK = "40"
NOTE_MARK_SIZE = 5.5
NOTE_MARK_RISE = 3.5
QUOTATION_MARK = '"'
HUNG_LINES = (1, 3)
QUOTED_PARAGRAPH_LINES = 5


def _baseline(row: int) -> float:
    return FIRST_ROW_BASELINE + row * LINE_PITCH


def _block(kind: str, html: str, span: tuple[float, float]) -> Block:
    top, bottom = span
    return Block(FILE_PAGE, kind, html, (LEFT - 2.0, top, RIGHT + 2.0, bottom), {}, f"/page/{FILE_PAGE}/{kind}/{top}")


class AbbreviationsPagePdf:
    def __init__(self, directory: Path) -> None:
        self._path = directory / "abbreviations.pdf"
        self._page = None
        self._row = 0

    def write_run_in_list(self) -> Path:
        return self._write(self._run_in_list)

    def write_run_in_list_raising_a_note_mark(self) -> Path:
        return self._write(self._run_in_list_raising_a_note_mark)

    def write_indented_paragraphs(self) -> Path:
        return self._write(self._indented_paragraphs)

    def write_hung_quotation_marks(self) -> Path:
        return self._write(self._hung_quotation_marks)

    def write_proof_steps(self) -> Path:
        return self._write(self._proof_steps)

    def _proof_steps(self) -> None:
        for step, depth in PROOF_STEPS:
            self._line(LEFT + depth * HANGING_INDENT, step)

    @property
    def rows(self) -> int:
        return self._row

    def _write(self, draw_rows) -> Path:
        with pymupdf.open() as document:
            self._page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            self._page.insert_text((LEFT, HEADING_BASELINE), HEADING_TITLE, fontsize=HEADING_SIZE,
                                   fontname=HEADING_FONT)
            draw_rows()
            document.save(self._path)
        return self._path

    def _run_in_list(self) -> None:
        for opening, run_on in RUN_IN_ENTRIES:
            self._line(LEFT, opening)
            self._line(LEFT + HANGING_INDENT, run_on)

    def _run_in_list_raising_a_note_mark(self) -> None:
        self._run_in_list()
        last_line = RUN_IN_ENTRIES[-1][-1]
        line_end = LEFT + HANGING_INDENT + pymupdf.get_text_length(last_line, fontname=EVEN_FONT, fontsize=BODY_SIZE)
        self._page.insert_text((line_end, _baseline(self._row - 1) - NOTE_MARK_RISE), NOTE_MARK,
                               fontsize=NOTE_MARK_SIZE, fontname=EVEN_FONT)

    def _indented_paragraphs(self) -> None:
        for _paragraph in range(PARAGRAPHS):
            self._line(LEFT + PARAGRAPH_INDENT, INDENTED_LINE)
            for line in RAGGED_LINES:
                self._line(LEFT, line)
            self._line(LEFT, CLOSING_LINE)

    def _hung_quotation_marks(self) -> None:
        mark_width = pymupdf.get_text_length(QUOTATION_MARK, fontname=EVEN_FONT, fontsize=BODY_SIZE)
        for line in range(QUOTED_PARAGRAPH_LINES):
            if line in HUNG_LINES:
                self._line(LEFT - mark_width, QUOTATION_MARK + FULL_LINE)
            else:
                self._line(LEFT, FULL_LINE)

    def _line(self, left: float, text: str) -> None:
        self._page.insert_text((left, _baseline(self._row)), text, fontsize=BODY_SIZE, fontname=EVEN_FONT)
        self._row += 1


def engine_reading(kind: str, html: str, rows: int) -> DocumentBlocks:
    heading = _block(HEADING_KIND, f"<h1>{HEADING_TITLE}</h1>", (HEADING_BASELINE - HEADING_SIZE, HEADING_BASELINE + 4))
    body = _block(kind, html, (FIRST_ROW_BASELINE - LINE_PITCH, _baseline(rows - 1) + 3))
    return DocumentBlocks([PageBlocks(FILE_PAGE, [heading, body])])


class TestExtractLabelListsRunningEachLabelIntoTheFirstLineOfItsEntry(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._pdf = AbbreviationsPagePdf(Path(directory.name))

    def _paragraphs_below_the_heading(self, pdf_path: Path, html: str, kind: str = TEXT_KIND) -> list[str]:
        layer = TextLayer(pdf_path)
        self.addCleanup(layer.close)
        inputs = StructureInputs(engine_reading(kind, html, self._pdf.rows), [], WorkerReadings.none(), keep_everything())
        structure = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)
        text = NoteWriter().render(structure.elements(), structure.definitions()).text
        paragraphs = [" ".join(paragraph.split()) for paragraph in text.strip().split("\n\n")]
        return paragraphs[paragraphs.index(f"# {HEADING_TITLE}") + 1:]

    def test_each_label_opens_an_entry_whose_run_on_lines_hang_beneath_it(self) -> None:
        pdf_path = self._pdf.write_run_in_list()
        html = f"<p>{' '.join(line for entry in RUN_IN_ENTRIES for line in entry)}</p>"
        self.assertEqual([" ".join(entry) for entry in RUN_IN_ENTRIES], self._paragraphs_below_the_heading(pdf_path, html))

    def test_ragged_paragraphs_opening_on_an_indent_are_each_a_paragraph_and_not_read_as_run_in_labels(self) -> None:
        pdf_path = self._pdf.write_indented_paragraphs()
        paragraph = " ".join([INDENTED_LINE, *RAGGED_LINES, CLOSING_LINE])
        html = f"<p>{' '.join([paragraph] * PARAGRAPHS)}</p>"
        self.assertEqual([paragraph] * PARAGRAPHS, self._paragraphs_below_the_heading(pdf_path, html))

    def test_lines_hung_into_the_margin_by_a_quotation_mark_leave_the_paragraph_whole(self) -> None:
        pdf_path = self._pdf.write_hung_quotation_marks()
        html = f"<p>{' '.join([FULL_LINE] * QUOTED_PARAGRAPH_LINES)}</p>"
        self.assertEqual(1, len(self._paragraphs_below_the_heading(pdf_path, html)))

    def test_a_block_the_engine_reads_as_a_list_item_keeps_the_engines_reading(self) -> None:
        pdf_path = self._pdf.write_run_in_list()
        html = f"<li>{' '.join(line for entry in RUN_IN_ENTRIES for line in entry)}</li>"
        self.assertEqual(1, len(self._paragraphs_below_the_heading(pdf_path, html, LIST_ITEM_KIND)))

    def test_a_list_raising_a_note_mark_keeps_the_engines_reading(self) -> None:
        pdf_path = self._pdf.write_run_in_list_raising_a_note_mark()
        html = f"<p>{' '.join(line for entry in RUN_IN_ENTRIES for line in entry)}<sup>{NOTE_MARK}</sup></p>"
        self.assertEqual(1, len(self._paragraphs_below_the_heading(pdf_path, html)))

    def test_steps_closing_their_sentence_above_an_indented_step_keep_the_engines_reading(self) -> None:
        pdf_path = self._pdf.write_proof_steps()
        html = f"<p>{' '.join(step for step, _depth in PROOF_STEPS)}</p>"
        self.assertEqual(1, len(self._paragraphs_below_the_heading(pdf_path, html)))


if __name__ == "__main__":
    unittest.main()
