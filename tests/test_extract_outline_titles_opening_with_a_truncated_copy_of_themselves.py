from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.elements import Heading, Paragraph
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.outline import Outline
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

FONT = "helv"
HEADING_SIZE = 14.0
BODY_SIZE = 10.0
LEFT = 40.0
RIGHT = 400.0
FIRST_BASELINE = 80.0
LINE_PITCH = 40.0
LINE_HALF_HEIGHT = 6.0
PRINTED_TITLE = "11.5 Theses Revisited"
GARBLED_TITLE = "11.5 Th11.5 Theses Revisited"
REPEATING_TITLE = "Tora! Tora! Tora!"
DOUBLED_WORD_TITLE = "New New York"
OPENING = "The metatheorem closes the previous section."
SENTENCE = "As we explained in our previous lecture, the logic of names is reducible."


class SectionPdf:
    def __init__(self, path: Path, outline_title: str) -> None:
        self._path = path
        self._outline_title = outline_title
        self._lines = [(TEXT_KIND, OPENING, BODY_SIZE), (HEADING_KIND, PRINTED_TITLE, HEADING_SIZE),
                       (TEXT_KIND, SENTENCE, BODY_SIZE)]

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            for row, (_kind, text, size) in enumerate(self._lines):
                page.insert_text((LEFT, _baseline(row)), text, fontsize=size, fontname=FONT)
            document.set_toc([[1, self._outline_title, 1]])
            document.save(self._path)
        return self._path

    def blocks(self) -> DocumentBlocks:
        return DocumentBlocks([PageBlocks(1, [_engine_block(row, line) for row, line in enumerate(self._lines)])])


def _baseline(row: int) -> float:
    return FIRST_BASELINE + row * LINE_PITCH


def _engine_block(row: int, line: tuple[str, str, float]) -> Block:
    kind, text, size = line
    baseline = _baseline(row)
    box = (LEFT, baseline - size - LINE_HALF_HEIGHT, RIGHT, baseline + LINE_HALF_HEIGHT)
    tag = "h3" if kind == HEADING_KIND else "p"
    return Block(1, kind, f"<{tag}>{text}</{tag}>", box, {}, f"/page/1/{kind}/{row}")


class TestOutlineTitlesOpeningWithATruncatedCopyOfThemselves(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._directory = Path(directory.name)

    def _titles(self, outline_title: str) -> list[str]:
        pdf_path = SectionPdf(self._directory / "section.pdf", outline_title).write()
        return [heading.title for heading in Outline(pdf_path).headings()]

    def test_the_outline_reads_a_title_from_where_its_copy_begins_again(self) -> None:
        self.assertEqual([PRINTED_TITLE], self._titles(GARBLED_TITLE))

    def test_the_outline_keeps_a_title_repeating_whole_words(self) -> None:
        self.assertEqual([REPEATING_TITLE], self._titles(REPEATING_TITLE))

    def test_the_outline_keeps_a_title_doubling_its_first_word(self) -> None:
        self.assertEqual([DOUBLED_WORD_TITLE], self._titles(DOUBLED_WORD_TITLE))

    def test_the_heading_is_written_once_where_the_page_prints_it(self) -> None:
        pdf = SectionPdf(self._directory / "section.pdf", GARBLED_TITLE)
        pdf_path = pdf.write()
        layer = TextLayer(pdf_path)
        self.addCleanup(layer.close)
        inputs = StructureInputs(pdf.blocks(), Outline(pdf_path).headings(), WorkerReadings.none(), keep_everything())
        elements = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs).elements()
        written = [element.title if isinstance(element, Heading) else element.text for element in elements
                   if isinstance(element, (Heading, Paragraph))]
        self.assertEqual([OPENING, PRINTED_TITLE, SENTENCE], written)


if __name__ == "__main__":
    unittest.main()
