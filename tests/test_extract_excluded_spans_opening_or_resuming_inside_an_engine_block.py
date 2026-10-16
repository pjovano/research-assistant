from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import page_assembler
from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, PageBlocks
from _extract.layer import TextLayer
from _extract.outline import Heading as OutlineHeading
from _extract.policy import SectionPolicy
from _extract.spans import ScopePoints
from _extract.structure import Paragraph
from _extract.withheld import WithheldNote

FILE_PAGE = 1
FONT = "tiro"
FONT_SIZE = 10.0
LINE_PITCH = 12.5
FIRST_BASELINE = 100.0
MARGIN = 60.0
PAGE_WIDTH, PAGE_HEIGHT = 400.0, 600.0
SUBLEVEL = 2
KEPT_LINES = ["An abbreviated version of the second chapter was published",
              "in a quarterly, and an early version of the fifth chapter",
              "was published in a review."]
EXCLUDED_LINES = ["I would like to thank the editors of both journals for",
                  "their permission to reprint these pieces here."]
NEXT_PAGE = "2"
NOTES_TITLE, REFERENCES_TITLE = "Notes", "References"
ENDNOTES = ["1. A note on the argument.", "2. My thanks to a colleague for pressing this point.",
            "3. A note on the conclusion."]
THANKS_NOTE = ENDNOTES[1]


class OnePageParagraphPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self, lines: list[str]) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            for row, text in enumerate(lines):
                page.insert_text((MARGIN, FIRST_BASELINE + row * LINE_PITCH), text, fontsize=FONT_SIZE,
                                 fontname=FONT)
            document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            document.save(self._path)
        return self._path


def one_engine_block(layer: TextLayer, lines: list[str]) -> Block:
    box = layer.lines(FILE_PAGE)[0].box
    bottom = FIRST_BASELINE + len(lines) * LINE_PITCH
    return Block(FILE_PAGE, "Text", f"<p>{' '.join(lines)}</p>", (box.left, box.top, PAGE_WIDTH - MARGIN, bottom),
                 {}, f"/page/{FILE_PAGE}/Text/0")


class TestExcludedSpansOpeningOrResumingInsideAnEngineBlock(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._path = Path(directory.name) / "paragraph.pdf"

    def paragraphs(self, lines: list[str], span: tuple[str, str]) -> list[str]:
        layer = TextLayer(OnePageParagraphPdf(self._path).write(lines))
        self.addCleanup(layer.close)
        policy = SectionPolicy(ScopePoints(layer).spans([span]))
        page = PageBlocks(FILE_PAGE, [one_engine_block(layer, lines)])
        elements = page_assembler(layer, policy).assemble(page, [], SUBLEVEL).elements
        return [element.text for element in elements if isinstance(element, Paragraph)]

    def test_the_lines_of_an_engine_block_above_a_span_opening_inside_it_are_kept(self) -> None:
        span = (f"{FILE_PAGE}: {EXCLUDED_LINES[0]}", NEXT_PAGE)
        self.assertEqual([" ".join(KEPT_LINES)], self.paragraphs(KEPT_LINES + EXCLUDED_LINES, span))

    def test_the_lines_of_an_engine_block_below_a_span_resuming_inside_it_are_kept(self) -> None:
        span = (str(FILE_PAGE), f"{FILE_PAGE}: {KEPT_LINES[0]}")
        self.assertEqual([" ".join(KEPT_LINES)], self.paragraphs(EXCLUDED_LINES + KEPT_LINES, span))


class EndnotesPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            for row, text in enumerate([NOTES_TITLE, *ENDNOTES, REFERENCES_TITLE]):
                page.insert_text((MARGIN, FIRST_BASELINE + 2 * row * LINE_PITCH), text, fontsize=FONT_SIZE,
                                 fontname=FONT)
            document.save(self._path)
        return self._path


def one_block_per_line(layer: TextLayer) -> list[Block]:
    lines = layer.lines(FILE_PAGE)
    kinds = [HEADING_KIND, *[TEXT_KIND] * len(ENDNOTES), HEADING_KIND]
    return [Block(FILE_PAGE, kind, "", (line.x0, line.y0, line.x1, 2 * line.center[1] - line.y0), {},
                  f"/page/{FILE_PAGE}/{kind}/{index}") for index, (kind, line) in enumerate(zip(kinds, lines))]


class TestEndnoteBlocksAnExcludedSpanCoversWhole(unittest.TestCase):
    def test_an_endnote_block_a_span_covers_whole_is_not_withheld_as_it_is_passed_over(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(EndnotesPdf(Path(directory.name) / "notes.pdf").write())
        self.addCleanup(layer.close)
        policy = SectionPolicy(ScopePoints(layer).spans([(f"{FILE_PAGE}: {THANKS_NOTE}",
                                                          f"{FILE_PAGE}: {ENDNOTES[2]}")]))
        assembler = page_assembler(layer, policy)
        due = [OutlineHeading(1, NOTES_TITLE, FILE_PAGE), OutlineHeading(1, REFERENCES_TITLE, FILE_PAGE)]
        assembler.assemble(PageBlocks(FILE_PAGE, one_block_per_line(layer)), due, None)
        self.assertNotIn(WithheldNote(FILE_PAGE, "2", True), assembler.withheld_notes())


if __name__ == "__main__":
    unittest.main()
