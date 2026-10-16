from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import BlockPlace, keep_everything, page_assembler
from _extract.blocks import CAPTION_KIND, HEADING_KIND, IMAGE_KINDS, TEXT_KIND, Block, PageBlocks
from _extract.layer import TextLayer
from _extract.structure import Heading, Paragraph

FONT = "tiro"
BODY_SIZE = 10.0
LEFT = 40.0
RIGHT = 500.0
CENTRED_LEFT = 180.0
LINE_HALF_HEIGHT = 6.0
FILE_PAGE = 1
SUBLEVEL = 3
OPENING = "So much for what nature does for its own end with respect to the human race as a class."
TITLE = "The prospective argument"
CLOSING = "In the second part of his reflections the author turns to the question of what is essential."
OPENING_BASELINE = 80.0
TITLE_BASELINE = 120.0
CLOSING_BASELINE = 160.0
FIGURE_BOX = (LEFT, 200.0, RIGHT, 400.0)


class CentredTitlePdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=RIGHT + LEFT)
            for left, baseline, text in [(LEFT, OPENING_BASELINE, OPENING), (CENTRED_LEFT, TITLE_BASELINE, TITLE),
                                         (LEFT, CLOSING_BASELINE, CLOSING)]:
                page.insert_text((left, baseline), text, fontsize=BODY_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


def line_box(left: float, baseline: float) -> tuple:
    return (left, baseline - BODY_SIZE - LINE_HALF_HEIGHT, RIGHT, baseline + LINE_HALF_HEIGHT)


def engine_reading() -> list[Block]:
    title_box = line_box(CENTRED_LEFT, TITLE_BASELINE)
    return [BlockPlace(line_box(LEFT, OPENING_BASELINE), 0).block(TEXT_KIND, f"<p>{OPENING}</p>"),
            BlockPlace(title_box, 1).block(CAPTION_KIND, f"<p>{TITLE}</p>"),
            BlockPlace(title_box, 2).block(HEADING_KIND, ""),
            BlockPlace(line_box(LEFT, CLOSING_BASELINE), 3).block(TEXT_KIND, f"<p>{CLOSING}</p>")]


class TestCaptionsTheEngineAlsoReadsAsAnEmptyHeadingOnAPageWithoutAFigure(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._layer = TextLayer(CentredTitlePdf(Path(directory.name) / "title.pdf").write())
        self.addCleanup(self._layer.close)

    def _written(self, blocks: list[Block]) -> list[tuple[str, str]]:
        result = page_assembler(self._layer, keep_everything()).assemble(PageBlocks(FILE_PAGE, blocks), [], SUBLEVEL)
        return [(type(element).__name__, element.title if isinstance(element, Heading) else element.text)
                for element in result.elements if isinstance(element, (Heading, Paragraph))]

    def test_the_caption_is_written_as_the_heading_the_engine_left_empty(self) -> None:
        self.assertEqual([(Paragraph.__name__, OPENING), (Heading.__name__, TITLE), (Paragraph.__name__, CLOSING)],
                         self._written(engine_reading()))

    def test_a_caption_on_a_page_holding_a_figure_stays_a_caption(self) -> None:
        figure = BlockPlace(FIGURE_BOX, 4).block(IMAGE_KINDS[0], "")
        self.assertIn((Paragraph.__name__, TITLE), self._written(engine_reading() + [figure]))


if __name__ == "__main__":
    unittest.main()
