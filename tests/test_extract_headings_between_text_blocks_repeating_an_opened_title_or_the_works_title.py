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
ITALIC_FONT = "heit"
HEADING_SIZE = 14.0
CAPTION_SIZE = 11.0
BODY_SIZE = 10.0
LEFT = 40.0
RIGHT = 400.0
FIRST_BASELINE = 80.0
LINE_PITCH = 40.0
LINE_HALF_HEIGHT = 6.0
WORK_TITLE = "Second Treatise of Government"
CHAPTER_TITLE = "8. Philosophical Skepticism and Externalist Epistemology"
SECTION_TITLE = "I. Philosophical Skepticism"
CAPTION = "Philosophical Skepticism"
NOTE_TITLE = "Note On The Text"
OPENING = "We consider the following thesis and its supporting argument."
CLOSING = "There is no way we could ever attain full philosophical understanding of our knowledge."


class CaptionedPagePdf:
    def __init__(self, path: Path, lines: list[tuple[str, str, float, str]]) -> None:
        self._path = path
        self._lines = lines

    def write(self, outline_title: str) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            for row, (_kind, text, size, font) in enumerate(self._lines):
                page.insert_text((LEFT, _baseline(row)), text, fontsize=size, fontname=font)
            document.set_toc([[1, outline_title, 1]])
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
    tag = "h3" if kind == HEADING_KIND else "p"
    return Block(1, kind, f"<{tag}>{text}</{tag}>", box, {}, f"/page/1/{kind}/{row}")


def _heading(text: str, size: float = HEADING_SIZE, font: str = FONT) -> tuple[str, str, float, str]:
    return (HEADING_KIND, text, size, font)


def _text(text: str) -> tuple[str, str, float, str]:
    return (TEXT_KIND, text, BODY_SIZE, FONT)


class TestHeadingsBetweenTextBlocksRepeatingAnOpenedTitleOrTheWorksTitle(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._directory = Path(directory.name)

    def _written(self, lines: list[tuple[str, str, float, str]], outline_title: str) -> list[tuple[str, str]]:
        pdf = CaptionedPagePdf(self._directory / "captioned.pdf", lines)
        pdf_path = pdf.write(outline_title)
        layer = TextLayer(pdf_path)
        self.addCleanup(layer.close)
        inputs = StructureInputs(pdf.blocks(), Outline(pdf_path).headings(), WorkerReadings.none(), keep_everything())
        work = WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts(), WORK_TITLE)
        elements = NoteStructure(work, inputs).elements()
        return [(type(element).__name__, element.title if isinstance(element, Heading) else element.text)
                for element in elements if isinstance(element, (Heading, Paragraph))]

    def test_a_caption_repeating_the_opened_section_title_between_paragraphs_is_kept_as_a_heading(self) -> None:
        lines = [_heading(CHAPTER_TITLE), _heading(SECTION_TITLE), _text(OPENING),
                 _heading(CAPTION, CAPTION_SIZE, ITALIC_FONT), _text(CLOSING)]
        expected = [(Heading.__name__, CHAPTER_TITLE), (Heading.__name__, SECTION_TITLE), (Paragraph.__name__, OPENING),
                    (Heading.__name__, CAPTION), (Paragraph.__name__, CLOSING)]
        self.assertEqual(expected, self._written(lines, CHAPTER_TITLE))

    def test_a_subheading_naming_the_work_between_paragraphs_is_kept_as_a_heading(self) -> None:
        lines = [_heading(NOTE_TITLE), _text(OPENING), _heading(WORK_TITLE, CAPTION_SIZE, ITALIC_FONT), _text(CLOSING)]
        expected = [(Heading.__name__, NOTE_TITLE), (Paragraph.__name__, OPENING), (Heading.__name__, WORK_TITLE),
                    (Paragraph.__name__, CLOSING)]
        self.assertEqual(expected, self._written(lines, NOTE_TITLE))

    def test_a_heading_naming_the_work_above_the_pages_text_is_dropped_as_the_running_head(self) -> None:
        lines = [_heading(WORK_TITLE, CAPTION_SIZE, ITALIC_FONT), _heading(NOTE_TITLE), _text(OPENING)]
        expected = [(Heading.__name__, NOTE_TITLE), (Paragraph.__name__, OPENING)]
        self.assertEqual(expected, self._written(lines, NOTE_TITLE))


if __name__ == "__main__":
    unittest.main()
