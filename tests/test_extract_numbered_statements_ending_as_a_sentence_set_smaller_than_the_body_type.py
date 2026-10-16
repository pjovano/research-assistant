from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import BlockPlace, keep_everything, page_assembler
from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, PageBlocks
from _extract.layer import TextLayer
from _extract.structure import Heading, Paragraph

FONT = "tiro"
BOLD_FONT = "tibo"
BODY_SIZE = 10.0
SMALLER_SIZE = 8.5
LEFT = 40.0
RIGHT = 500.0
LINE_HALF_HEIGHT = 6.0
FILE_PAGE = 1
SUBLEVEL = 2
LEAD_IN = "Thus, the following important consequence of the first thesis should be noted:"
FOLLOWING = "As textual support of this thesis we note the following passage from the Ideas."
THESIS = "8. Noemata are abstract entities."
UNFINISHED_TITLE = "8. Noemata as abstract entities"
LEAD_IN_BASELINE = 80.0
THESIS_BASELINE = 110.0
FOLLOWING_BASELINE = 140.0


@dataclass(frozen=True)
class StatementSetting:
    text: str
    size: float
    font: str = FONT


class StatementPagePdf:
    def __init__(self, path: Path, statement: StatementSetting) -> None:
        self._path = path
        self._statement = statement

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=RIGHT + LEFT)
            statement = self._statement
            lines = [(LEAD_IN_BASELINE, LEAD_IN, BODY_SIZE, FONT),
                     (THESIS_BASELINE, statement.text, statement.size, statement.font),
                     (FOLLOWING_BASELINE, FOLLOWING, BODY_SIZE, FONT)]
            for baseline, text, size, font in lines:
                page.insert_text((LEFT, baseline), text, fontsize=size, fontname=font)
            document.save(self._path)
        return self._path


def line_box(baseline: float) -> tuple:
    return (LEFT, baseline - BODY_SIZE - LINE_HALF_HEIGHT / 2, RIGHT, baseline + LINE_HALF_HEIGHT / 2)


def engine_reading(statement: str) -> list[Block]:
    return [BlockPlace(line_box(LEAD_IN_BASELINE), 0).block(TEXT_KIND, f"<p>{LEAD_IN}</p>"),
            BlockPlace(line_box(THESIS_BASELINE), 1).block(HEADING_KIND, f"<h4>{statement}</h4>"),
            BlockPlace(line_box(FOLLOWING_BASELINE), 2).block(TEXT_KIND, f"<p>{FOLLOWING}</p>")]


class TestNumberedStatementsEndingAsASentenceSetSmallerThanTheBodyType(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._directory = Path(directory.name)

    def _written(self, statement: StatementSetting) -> list[tuple[str, str]]:
        layer = TextLayer(StatementPagePdf(self._directory / "statement.pdf", statement).write())
        self.addCleanup(layer.close)
        page = PageBlocks(FILE_PAGE, engine_reading(statement.text))
        result = page_assembler(layer, keep_everything()).assemble(page, [], SUBLEVEL)
        return [(type(element).__name__, element.title if isinstance(element, Heading) else element.text)
                for element in result.elements if isinstance(element, (Heading, Paragraph))]

    def test_a_numbered_statement_set_smaller_than_the_body_is_written_as_a_line(self) -> None:
        self.assertIn((Paragraph.__name__, THESIS), self._written(StatementSetting(THESIS, SMALLER_SIZE)))

    def test_a_numbered_statement_set_in_the_body_size_stays_a_heading(self) -> None:
        self.assertIn((Heading.__name__, THESIS), self._written(StatementSetting(THESIS, BODY_SIZE)))

    def test_a_smaller_numbered_title_not_ending_as_a_sentence_stays_a_heading(self) -> None:
        written = self._written(StatementSetting(UNFINISHED_TITLE, SMALLER_SIZE))
        self.assertIn((Heading.__name__, UNFINISHED_TITLE), written)

    def test_a_smaller_numbered_statement_in_a_weight_apart_from_the_body_stays_a_heading(self) -> None:
        self.assertIn((Heading.__name__, THESIS), self._written(StatementSetting(THESIS, SMALLER_SIZE, BOLD_FONT)))


if __name__ == "__main__":
    unittest.main()
