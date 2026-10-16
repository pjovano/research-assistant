from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import BlockPlace, PrintedWork, keep_everything, page_assembler
from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, PageBlocks
from _extract.layer import TextLayer
from _extract.structure import Heading, Paragraph

FONT = "cour"
INVISIBLE = 3
VISIBLE = 0
LEFT = 40.0
RIGHT = 560.0
LINE_HALF_HEIGHT = 5.0
FILE_PAGE = 1
SUBLEVEL = 2
EXAMPLE = "(11) Superman is Clark Kent."
BODY_LINES = [("The real problem is that certain claims must be ruled false:", 9.0, 80.0),
              ("Superman picks out one temporal phase, and Clark another.", 9.0, 140.0),
              ("This is clearly not an acceptable result of the account.", 10.0, 160.0)]
EXAMPLE_BASELINE = 110.0
SIZE_WITHIN_THE_BODY_LINES = 10.0
SIZE_ABOVE_THE_BODY_LINES = 14.0


@dataclass(frozen=True)
class PageSetting:
    render_mode: int
    example_size: float


class UnevenlyMeasuredPagePdf:
    def __init__(self, path: Path, setting: PageSetting) -> None:
        self._path = path
        self._setting = setting

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=RIGHT + LEFT)
            for text, size, baseline in BODY_LINES + [(EXAMPLE, self._setting.example_size, EXAMPLE_BASELINE)]:
                page.insert_text((LEFT, baseline), text, fontsize=size, fontname=FONT,
                                 render_mode=self._setting.render_mode)
            document.save(self._path)
        return self._path


def line_box(size: float, baseline: float) -> tuple:
    return (LEFT, baseline - size - LINE_HALF_HEIGHT / 2, RIGHT, baseline + LINE_HALF_HEIGHT / 2)


def engine_reading(example_size: float) -> list[Block]:
    body = [BlockPlace(line_box(size, baseline), index).block(TEXT_KIND, f"<p>{text}</p>")
            for index, (text, size, baseline) in enumerate(BODY_LINES)]
    example = BlockPlace(line_box(example_size, EXAMPLE_BASELINE), len(body)).block(HEADING_KIND, f"<h4>{EXAMPLE}</h4>")
    return body + [example]


class TestNumberedDisplayLinesOnATextLayerNotDrawnMeasuringItsLinesUnevenly(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._directory = Path(directory.name)

    def _written(self, setting: PageSetting, printed: PrintedWork) -> list[tuple[str, str]]:
        layer = TextLayer(UnevenlyMeasuredPagePdf(self._directory / "page.pdf", setting).write())
        self.addCleanup(layer.close)
        page = PageBlocks(FILE_PAGE, engine_reading(setting.example_size))
        result = page_assembler(layer, keep_everything(), printed).assemble(page, [], SUBLEVEL)
        return [(type(element).__name__, element.title if isinstance(element, Heading) else element.text)
                for element in result.elements if isinstance(element, (Heading, Paragraph))]

    def _written_from_pixels(self, example_size: float) -> list[tuple[str, str]]:
        return self._written(PageSetting(INVISIBLE, example_size), PrintedWork(pixel_pages=frozenset({FILE_PAGE})))

    def test_an_example_measured_within_the_sizes_of_the_body_lines_is_written_as_a_line(self) -> None:
        self.assertIn((Paragraph.__name__, EXAMPLE), self._written_from_pixels(SIZE_WITHIN_THE_BODY_LINES))

    def test_an_example_measured_above_the_sizes_of_the_body_lines_stays_a_heading(self) -> None:
        self.assertIn((Heading.__name__, EXAMPLE), self._written_from_pixels(SIZE_ABOVE_THE_BODY_LINES))

    def test_on_a_drawn_text_layer_an_example_apart_from_the_body_type_stays_a_heading(self) -> None:
        written = self._written(PageSetting(VISIBLE, SIZE_WITHIN_THE_BODY_LINES), PrintedWork())
        self.assertIn((Heading.__name__, EXAMPLE), written)


if __name__ == "__main__":
    unittest.main()
