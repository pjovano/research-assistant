from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Callable

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import keep_everything, page_assembler
from _extract.blocks import TEXT_KIND, Block, PageBlocks
from _extract.layer import TextLayer
from _extract.structure import Paragraph, Verbatim

FILE_PAGE = 1
FONT = "tiro"
FONT_SIZE = 10.0
PAGE_WIDTH, PAGE_HEIGHT = 440.0, 600.0
TEXT_LEFT = 80.0
BULLET_LEFT = 66.0
BULLET_SIDE = 4.0
BULLET_RISE = 3.0
RIGHT = 380.0
FIRST_BASELINE = 100.0
ITEM_PITCH = 17.0
WRAP_PITCH = 13.0
ABOVE_BASELINE = 9.0
BELOW_BASELINE = 3.0
SUBLEVEL = 1
BLACK = (0.0, 0.0, 0.0)
WHITE = (1.0, 1.0, 1.0)
GREY = (0.85, 0.85, 0.85)
LINE_NUMBER_LEFT = 60.0
LINE_NUMBER_BOX_WIDTH = 12.0
PROSE_LINES = ["The charge of solipsism was raised against the doctrine of science as soon",
               "as it appeared, and a letter of that year already calls the position a",
               "philosophical egoism that cannot reach out to a world of real objects."]
ITEMS = [["There is no absolute simultaneity independent of the observer"],
         ["There is a clock paradox even for observers on geodesic trajecto-", "ries"],
         ["There is a length contraction of moving bodies"]]
JOINED_ITEMS = ["There is no absolute simultaneity independent of the observer",
                "There is a clock paradox even for observers on geodesic trajectories",
                "There is a length contraction of moving bodies"]


def filled_square(page: pymupdf.Page, baseline: float) -> None:
    top = baseline - BULLET_RISE - BULLET_SIDE
    page.draw_rect(pymupdf.Rect(BULLET_LEFT, top, BULLET_LEFT + BULLET_SIDE, top + BULLET_SIDE), color=None, fill=BLACK)


def thick_stroke(page: pymupdf.Page, baseline: float) -> None:
    middle = BULLET_LEFT + BULLET_SIDE / 2
    bottom = baseline - BULLET_RISE
    page.draw_line((middle, bottom), (middle, bottom - BULLET_SIDE), color=BLACK, width=BULLET_SIDE)


def white_square(page: pymupdf.Page, baseline: float) -> None:
    top = baseline - ABOVE_BASELINE
    page.draw_rect(pymupdf.Rect(BULLET_LEFT, top, BULLET_LEFT + BULLET_SIDE, top + BULLET_SIDE), color=WHITE, fill=WHITE)


class LineNumberedProsePdf:
    def __init__(self, path: Path, box_fill: tuple[float, float, float]) -> None:
        self._path = path
        self._box_fill = box_fill

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            for number, (baseline, line) in enumerate(zip(prose_baselines(), PROSE_LINES), start=1):
                box = pymupdf.Rect(LINE_NUMBER_LEFT - 2.0, baseline - ABOVE_BASELINE,
                                   LINE_NUMBER_LEFT + LINE_NUMBER_BOX_WIDTH, baseline + BELOW_BASELINE)
                page.draw_rect(box, color=None, fill=self._box_fill)
                page.insert_text((LINE_NUMBER_LEFT, baseline), str(number), fontsize=FONT_SIZE, fontname=FONT)
                page.insert_text((TEXT_LEFT, baseline), line, fontsize=FONT_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


def prose_baselines() -> list[float]:
    return [FIRST_BASELINE + row * WRAP_PITCH for row in range(len(PROSE_LINES))]


def prose_block() -> Block:
    box = (TEXT_LEFT - 2.0, FIRST_BASELINE - ABOVE_BASELINE, RIGHT, prose_baselines()[-1] + BELOW_BASELINE)
    return Block(FILE_PAGE, TEXT_KIND, f"<p>{' '.join(PROSE_LINES)}</p>", box, {}, f"/page/{FILE_PAGE}/Text/0")


class DrawnBulletListPdf:
    def __init__(self, path: Path, bullet: Callable[[pymupdf.Page, float], None]) -> None:
        self._path = path
        self._bullet = bullet

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            for opening, lines in zip(item_baselines(), ITEMS):
                self._bullet(page, opening)
                for offset, line in enumerate(lines):
                    page.insert_text((TEXT_LEFT, opening + offset * WRAP_PITCH), line, fontsize=FONT_SIZE,
                                     fontname=FONT)
            document.save(self._path)
        return self._path


def item_baselines() -> list[float]:
    baselines, baseline = [], FIRST_BASELINE
    for lines in ITEMS:
        baselines.append(baseline)
        baseline += (len(lines) - 1) * WRAP_PITCH + ITEM_PITCH
    return baselines


def engine_block() -> Block:
    last_baseline = item_baselines()[-1] + (len(ITEMS[-1]) - 1) * WRAP_PITCH
    box = (TEXT_LEFT - 2.0, FIRST_BASELINE - ABOVE_BASELINE, RIGHT, last_baseline + BELOW_BASELINE)
    return Block(FILE_PAGE, TEXT_KIND, f"<p>{' '.join(JOINED_ITEMS)}</p>", box, {}, f"/page/{FILE_PAGE}/Text/0")


class TestListsWhoseBulletsAreDrawnShapesAbsentFromTheTextLayer(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._path = Path(directory.name) / "bullets.pdf"

    def written(self, bullet: Callable[[pymupdf.Page, float], None]) -> list[str]:
        return self.assembled(DrawnBulletListPdf(self._path, bullet).write(), engine_block())

    def assembled(self, pdf: Path, block: Block) -> list[str]:
        layer = TextLayer(pdf)
        self.addCleanup(layer.close)
        result = page_assembler(layer, keep_everything()).assemble(PageBlocks(FILE_PAGE, [block]), [], SUBLEVEL)
        return [element.text for element in result.elements if isinstance(element, (Paragraph, Verbatim))]

    def test_each_row_beside_a_filled_square_opens_a_list_item(self) -> None:
        self.assertEqual([f"- {item}" for item in JOINED_ITEMS], self.written(filled_square))

    def test_each_row_beside_a_thick_short_stroke_opens_a_list_item(self) -> None:
        self.assertEqual([f"- {item}" for item in JOINED_ITEMS], self.written(thick_stroke))

    def test_rows_beside_white_squares_stay_one_paragraph(self) -> None:
        self.assertEqual([" ".join(JOINED_ITEMS)], self.written(white_square))

    def test_prose_beside_white_boxes_behind_its_line_numbers_stays_one_paragraph(self) -> None:
        written = self.assembled(LineNumberedProsePdf(self._path, WHITE).write(), prose_block())
        self.assertEqual([" ".join(PROSE_LINES)], written)

    def test_prose_beside_shaded_boxes_holding_its_line_numbers_stays_one_paragraph(self) -> None:
        written = self.assembled(LineNumberedProsePdf(self._path, GREY).write(), prose_block())
        self.assertEqual([" ".join(PROSE_LINES)], written)


if __name__ == "__main__":
    unittest.main()
