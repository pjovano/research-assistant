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

FONT = "tiro"
BOLD_FONT = "tibo"
HEADING_SIZE = 12.0
BODY_SIZE = 9.5
LEFT = 40.0
RIGHT = 500.0
FIRST_BASELINE = 80.0
LINE_PITCH = 40.0
LINE_HALF_HEIGHT = 6.0
BOOK_TITLE = "Book IX"
OPENING = "ATHENIAN: Next we turn to the suits that arise between the members of the several trades we have named."
REPLY = "CLINIAS: That's right."
CLOSING = "ATHENIAN: To write laws of this kind at all is, when one reflects on it, something of a reproach to a city."
BODY_TYPE_HEADING = "The Proceedings of the Courts"
BOLD_SENTENCE_HEADING = "The courts are to be feared."


class DialoguePagePdf:
    def __init__(self, path: Path, lines: list[tuple[str, str, float, str]]) -> None:
        self._path = path
        self._lines = lines

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=RIGHT + LEFT)
            for row, (_kind, text, size, font) in enumerate(self._lines):
                page.insert_text((LEFT, _baseline(row)), text, fontsize=size, fontname=font)
            document.set_toc([[1, BOOK_TITLE, 1]])
            document.save(self._path)
        return self._path

    def blocks(self) -> DocumentBlocks:
        return DocumentBlocks([PageBlocks(1, [_engine_block(row, line) for row, line in enumerate(self._lines)])])


def _baseline(row: int) -> float:
    return FIRST_BASELINE + row * LINE_PITCH


def _engine_block(row: int, line: tuple[str, str, float, str]) -> Block:
    kind, text, size, _font = line
    baseline = _baseline(row)
    box = (LEFT, baseline - size - LINE_HALF_HEIGHT, RIGHT, baseline + LINE_HALF_HEIGHT)
    tag = "h1" if kind == HEADING_KIND else "p"
    return Block(1, kind, f"<{tag}>{text}</{tag}>", box, {}, f"/page/1/{kind}/{row}")


def _page(line_between: tuple[str, str, float, str]) -> list[tuple[str, str, float, str]]:
    return [(HEADING_KIND, BOOK_TITLE, HEADING_SIZE, FONT), (TEXT_KIND, OPENING, BODY_SIZE, FONT), line_between,
            (TEXT_KIND, CLOSING, BODY_SIZE, FONT)]


class TestHeadingBlocksSetInTheBodyTypeEndingAsASentence(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._directory = Path(directory.name)

    def _written(self, line_between: tuple[str, str, float, str]) -> list[tuple[str, str]]:
        pdf = DialoguePagePdf(self._directory / "dialogue.pdf", _page(line_between))
        pdf_path = pdf.write()
        layer = TextLayer(pdf_path)
        self.addCleanup(layer.close)
        inputs = StructureInputs(pdf.blocks(), Outline(pdf_path).headings(), WorkerReadings.none(), keep_everything())
        elements = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs).elements()
        return [(type(element).__name__, element.title if isinstance(element, Heading) else element.text)
                for element in elements if isinstance(element, (Heading, Paragraph))]

    def test_a_line_of_dialogue_the_engine_reads_as_a_heading_is_written_as_a_paragraph(self) -> None:
        written = self._written((HEADING_KIND, REPLY, BODY_SIZE, FONT))
        self.assertIn((Paragraph.__name__, REPLY), written)

    def test_a_heading_in_the_body_type_not_ending_as_a_sentence_stays_a_heading(self) -> None:
        written = self._written((HEADING_KIND, BODY_TYPE_HEADING, BODY_SIZE, FONT))
        self.assertIn((Heading.__name__, BODY_TYPE_HEADING), written)

    def test_a_heading_ending_as_a_sentence_in_a_type_apart_from_the_body_stays_a_heading(self) -> None:
        written = self._written((HEADING_KIND, BOLD_SENTENCE_HEADING, BODY_SIZE, BOLD_FONT))
        self.assertIn((Heading.__name__, BOLD_SENTENCE_HEADING), written)


if __name__ == "__main__":
    unittest.main()
