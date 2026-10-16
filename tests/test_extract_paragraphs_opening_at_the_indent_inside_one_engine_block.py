from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import keep_everything, page_assembler
from _extract.blocks import TEXT_KIND, Block, PageBlocks
from _extract.layer import TextLayer
from _extract.structure import Paragraph

FILE_PAGE = 1
FONT = "tiro"
FONT_SIZE = 10.0
MARK_SIZE = 7.0
PAGE_WIDTH, PAGE_HEIGHT = 440.0, 600.0
LEFT = 66.0
MARK_LEFT = 48.0
PARAGRAPH_INDENT = 10.0
RIGHT = 380.0
FIRST_BASELINE = 100.0
LINE_PITCH = 11.0
ABOVE_BASELINE = 9.0
BELOW_BASELINE = 3.0
SUBLEVEL = 1
OPENS, RUNS_ON = True, False
TURNS = [[(OPENS, "SOCRATES: Is the law kept because it is just, or for some"), (RUNS_ON, "other reason?")],
         [(OPENS, "EUTHYPHRO: For that reason alone.")],
         [(OPENS, "SOCRATES: Then it is kept because it is just, and it is not"),
          (RUNS_ON, "just because it is being kept?")],
         [(OPENS, "EUTHYPHRO: So it seems.")]]
MARKED_ROW = 2
MARGIN_MARK = "d"


def baseline(row: int) -> float:
    return FIRST_BASELINE + row * LINE_PITCH


def rows() -> list[tuple[bool, str]]:
    return [line for turn in TURNS for line in turn]


class DialoguePagePdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            for row, (opens, text) in enumerate(rows()):
                left = LEFT + PARAGRAPH_INDENT if opens else LEFT
                page.insert_text((left, baseline(row)), text, fontsize=FONT_SIZE, fontname=FONT)
            page.insert_text((MARK_LEFT, baseline(MARKED_ROW)), MARGIN_MARK, fontsize=MARK_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


def engine_block() -> Block:
    text = " ".join(text for _opens, text in rows())
    box = (MARK_LEFT, baseline(0) - ABOVE_BASELINE, RIGHT, baseline(len(rows()) - 1) + BELOW_BASELINE)
    return Block(FILE_PAGE, TEXT_KIND, f"<p>{text}</p>", box, {}, f"/page/{FILE_PAGE}/{TEXT_KIND}/0")


class TestParagraphsOpeningAtTheIndentInsideOneEngineBlock(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._path = Path(directory.name) / "dialogue.pdf"

    def paragraphs(self) -> list[str]:
        layer = TextLayer(DialoguePagePdf(self._path).write())
        self.addCleanup(layer.close)
        result = page_assembler(layer, keep_everything()).assemble(PageBlocks(FILE_PAGE, [engine_block()]), [],
                                                                   SUBLEVEL)
        return [element.text for element in result.elements if isinstance(element, Paragraph)]

    def test_each_line_opening_at_the_indent_below_a_closed_sentence_opens_a_paragraph(self) -> None:
        expected = [" ".join(text for _opens, text in turn) for turn in TURNS]
        expected[1] = f"{MARGIN_MARK} {expected[1]}"
        self.assertEqual(expected, self.paragraphs())


if __name__ == "__main__":
    unittest.main()
