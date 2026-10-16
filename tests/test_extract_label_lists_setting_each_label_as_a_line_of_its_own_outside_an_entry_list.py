from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import HEADING_KIND, LIST_GROUP_KIND, LIST_ITEM_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs
from _extract.writer import NoteWriter

HEADING_FONT = "helv"
LABEL_FONT = "tiit"
TEXT_FONT = "tiro"
EVEN_FONT = "cour"
FILE_PAGE = 1
PAGE_WIDTH, PAGE_HEIGHT = 432.0, 648.0
LEFT = 54.0
TEXT_LEFT = 110.0
RIGHT = 400.0
BODY_SIZE = 9.0
HEADING_SIZE = 16.0
LINE_PITCH = 12.0
HEADING_BASELINE = 60.0
FIRST_ROW_BASELINE = 100.5
HEADING_TITLE = "Abbreviations"
LABELLED_ENTRIES = (("A", ("Aesthetics, two volumes. Berlin and Weimar: Aufbau Verlag, 1965", "(cited by volume).")),
                    ("EL", ("The Encyclopaedia Logic, translated by T. F. Geraets and others.",
                            "Indianapolis: Hackett, 1991.")),
                    ("GW", ("Gesammelte Werke, edited for the Academy of Sciences, 22 volumes.",
                            "Hamburg: Felix Meiner, 1968.")))
EVEN_LINE = "word " * 9 + "word"
EVEN_LINES = 6
MARGIN_LABELS = {0: "A 51", 3: "B 75"}
PARAGRAPH_INDENT = 18.0
VERSE_LINES = ("Gives peace to men and stillness to the sea,", "Lays winds to rest, and careworn men to sleep.",
               "And sings his song to every living thing,", "Charming the mind of gods and men alike.")
MARGIN_LETTERS = {1: "d", 3: "e"}
INDENTED_PARAGRAPHS = (("The first paragraph opens on an indented line of words and", "runs on flush below it."),
                       ("The second paragraph opens on an indented line of words and", "runs on flush below it."),
                       ("The third paragraph opens on an indented line of words and", "runs on flush below it."))


def _baseline(row: int) -> float:
    return FIRST_ROW_BASELINE + row * LINE_PITCH


def _block(kind: str, html: str, span: tuple[float, float]) -> Block:
    top, bottom = span
    return Block(FILE_PAGE, kind, html, (LEFT - 2.0, top, RIGHT + 2.0, bottom), {}, f"/page/{FILE_PAGE}/{kind}/{top}")


class AbbreviationsPagePdf:
    def __init__(self, directory: Path) -> None:
        self._path = directory / "abbreviations.pdf"
        self._page = None

    def write_label_list(self) -> Path:
        return self._write(self._label_list)

    def write_margin_labels(self) -> Path:
        return self._write(self._margin_labels)

    def write_indented_paragraphs(self) -> Path:
        return self._write(self._indented_paragraphs)

    def write_verse_with_margin_letters(self) -> Path:
        return self._write(self._verse_with_margin_letters)

    def _write(self, draw_rows) -> Path:
        with pymupdf.open() as document:
            self._page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            self._page.insert_text((LEFT, HEADING_BASELINE), HEADING_TITLE, fontsize=HEADING_SIZE,
                                   fontname=HEADING_FONT)
            draw_rows()
            document.save(self._path)
        return self._path

    def _label_list(self) -> None:
        row = 0
        for label, lines in LABELLED_ENTRIES:
            self._text((LEFT, _baseline(row)), label, LABEL_FONT)
            for line in lines:
                self._text((TEXT_LEFT, _baseline(row)), line, TEXT_FONT)
                row += 1

    def _margin_labels(self) -> None:
        for row in range(EVEN_LINES):
            if row in MARGIN_LABELS:
                self._text((LEFT, _baseline(row)), MARGIN_LABELS[row], EVEN_FONT)
            self._text((TEXT_LEFT, _baseline(row)), EVEN_LINE, EVEN_FONT)

    def _verse_with_margin_letters(self) -> None:
        for row, line in enumerate(VERSE_LINES):
            if row in MARGIN_LETTERS:
                self._text((LEFT, _baseline(row)), MARGIN_LETTERS[row], TEXT_FONT)
            self._text((TEXT_LEFT, _baseline(row)), line, TEXT_FONT)

    def _indented_paragraphs(self) -> None:
        row = 0
        for opening, run_on in INDENTED_PARAGRAPHS:
            self._text((LEFT + PARAGRAPH_INDENT, _baseline(row)), opening, TEXT_FONT)
            self._text((LEFT, _baseline(row + 1)), run_on, TEXT_FONT)
            row += 2

    def _text(self, origin: tuple[float, float], text: str, font: str) -> None:
        self._page.insert_text(origin, text, fontsize=BODY_SIZE, fontname=font)


def engine_reading(kind: str, html: str, rows: int) -> DocumentBlocks:
    heading = _block(HEADING_KIND, f"<h1>{HEADING_TITLE}</h1>", (HEADING_BASELINE - HEADING_SIZE, HEADING_BASELINE + 4))
    body = _block(kind, html, (FIRST_ROW_BASELINE - LINE_PITCH, _baseline(rows - 1) + 3))
    return DocumentBlocks([PageBlocks(FILE_PAGE, [heading, body])])


class TestExtractLabelListsSettingEachLabelAsALineOfItsOwnOutsideAnEntryList(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._pdf = AbbreviationsPagePdf(Path(directory.name))

    def _paragraphs_below_the_heading(self, pdf_path: Path, blocks: DocumentBlocks) -> list[str]:
        layer = TextLayer(pdf_path)
        self.addCleanup(layer.close)
        inputs = StructureInputs(blocks, [], WorkerReadings.none(), keep_everything())
        structure = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)
        text = NoteWriter().render(structure.elements(), structure.definitions()).text
        paragraphs = [" ".join(paragraph.split()) for paragraph in text.strip().split("\n\n")]
        return paragraphs[paragraphs.index(f"# {HEADING_TITLE}") + 1:]

    def test_each_label_opens_an_entry_holding_the_text_wrapped_beside_it(self) -> None:
        rows = sum(len(lines) for _label, lines in LABELLED_ENTRIES)
        merged = " ".join(f"{label} {' '.join(lines)}" for label, lines in LABELLED_ENTRIES)
        paragraphs = self._paragraphs_below_the_heading(self._pdf.write_label_list(),
                                                        engine_reading(LIST_ITEM_KIND, f"<li>{merged}</li>", rows))
        self.assertEqual([" ".join([label, *lines]) for label, lines in LABELLED_ENTRIES], paragraphs)

    def test_a_block_the_engine_reads_as_a_list_group_keeps_the_engines_reading(self) -> None:
        rows = sum(len(lines) for _label, lines in LABELLED_ENTRIES)
        merged = " ".join(f"{label} {' '.join(lines)}" for label, lines in LABELLED_ENTRIES)
        paragraphs = self._paragraphs_below_the_heading(self._pdf.write_label_list(),
                                                        engine_reading(LIST_GROUP_KIND, f"<p>{merged}</p>", rows))
        self.assertEqual(1, len(paragraphs))

    def test_labels_beside_lines_that_run_on_leave_the_paragraph_whole(self) -> None:
        html = f"<p>{' '.join([EVEN_LINE] * EVEN_LINES)}</p>"
        paragraphs = self._paragraphs_below_the_heading(self._pdf.write_margin_labels(),
                                                        engine_reading(TEXT_KIND, html, EVEN_LINES))
        self.assertEqual(1, len(paragraphs))

    def test_letters_referring_to_a_line_from_the_margin_are_not_read_as_labels(self) -> None:
        html = f"<p>{' '.join(VERSE_LINES)}</p>"
        paragraphs = self._paragraphs_below_the_heading(self._pdf.write_verse_with_margin_letters(),
                                                        engine_reading(TEXT_KIND, html, len(VERSE_LINES)))
        self.assertEqual(1, len(paragraphs))

    def test_paragraphs_opening_on_an_indent_are_each_a_paragraph_and_not_read_as_labels(self) -> None:
        html = f"<p>{' '.join(line for lines in INDENTED_PARAGRAPHS for line in lines)}</p>"
        rows = 2 * len(INDENTED_PARAGRAPHS)
        paragraphs = self._paragraphs_below_the_heading(self._pdf.write_indented_paragraphs(),
                                                        engine_reading(TEXT_KIND, html, rows))
        self.assertEqual([" ".join(lines) for lines in INDENTED_PARAGRAPHS], paragraphs)


if __name__ == "__main__":
    unittest.main()
