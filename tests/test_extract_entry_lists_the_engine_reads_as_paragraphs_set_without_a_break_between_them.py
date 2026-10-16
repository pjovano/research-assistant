from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import PrintedWork, keep_everything, page_assembler
from _extract.blocks import Block, PageBlocks
from _extract.layer import TextLayer
from _extract.markdown import HtmlToMarkdown
from _extract.structure import Paragraph

FONT = "cour"
FONT_SIZE = 9.0
INVISIBLE = 3
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
REPEATED_AUTHOR_INDENT = 10.0
FILE_PAGE = 1
ENGINE_LIST_KIND = "ListGroup"
FIRST_BASELINE = 100.0
LINE_PITCH = 11.0
LINE_HALF_HEIGHT = 8.0
ENTRIES = [(0.0, "Adams, Anna 2005. Kant. Oxford: Blackwell."),
           (REPEATED_AUTHOR_INDENT, "2010. The Antinomies. Cambridge: Cambridge University Press."),
           (0.0, "Baker, Bernd 1992. Truth and Objectivity. Cambridge, MA: Harvard University Press."),
           (REPEATED_AUTHOR_INDENT, "1996. Realism, Meaning and Truth. Cambridge: Polity."),
           (0.0, "Carter, Clara 2014. God, Totality and Possibility. Kantian Review 19.1: 27-51.")]


class RecognizedBibliographyScanPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            for row, (indent, text) in enumerate(ENTRIES):
                page.insert_text((LEFT + indent, FIRST_BASELINE + row * LINE_PITCH), text, fontsize=FONT_SIZE,
                                 fontname=FONT, render_mode=INVISIBLE)
            document.save(self._path)
        return self._path


def entry_paragraphs_html(separator: str) -> str:
    return separator.join(f"<p>{text}</p>" for _indent, text in ENTRIES)


def engine_list_block(html_text: str) -> Block:
    last_baseline = FIRST_BASELINE + (len(ENTRIES) - 1) * LINE_PITCH
    box = (LEFT, FIRST_BASELINE - LINE_HALF_HEIGHT, RIGHT, last_baseline + LINE_HALF_HEIGHT / 2)
    return Block(FILE_PAGE, ENGINE_LIST_KIND, html_text, box, {}, f"/page/{FILE_PAGE}/{ENGINE_LIST_KIND}/0")


def entry_lines() -> list[str]:
    return [text for _indent, text in ENTRIES]


class TestEntryListsTheEngineReadsAsParagraphsSetWithoutABreakBetweenThem(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._layer = TextLayer(RecognizedBibliographyScanPdf(Path(directory.name) / "scan.pdf").write())
        self.addCleanup(self._layer.close)

    def _paragraph_lines(self, html_text: str) -> list[str]:
        assembler = page_assembler(self._layer, keep_everything(), PrintedWork(pixel_pages=frozenset({FILE_PAGE})))
        result = assembler.assemble(PageBlocks(FILE_PAGE, [engine_list_block(html_text)]), [], 1)
        paragraphs = [element.text for element in result.elements if isinstance(element, Paragraph)]
        return [line for paragraph in paragraphs for line in paragraph.split("\n")]

    def test_each_paragraph_set_flush_against_the_next_opens_a_line_of_its_own(self) -> None:
        self.assertEqual(entry_lines(), self._paragraph_lines(entry_paragraphs_html("")))

    def test_each_paragraph_set_on_a_line_below_the_last_opens_a_line_of_its_own(self) -> None:
        self.assertEqual(entry_lines(), self._paragraph_lines(entry_paragraphs_html("\n")))

    def test_a_single_paragraph_converts_to_its_text_alone(self) -> None:
        self.assertEqual(ENTRIES[0][1], HtmlToMarkdown().text(f"<p>{ENTRIES[0][1]}</p>"))


if __name__ == "__main__":
    unittest.main()
