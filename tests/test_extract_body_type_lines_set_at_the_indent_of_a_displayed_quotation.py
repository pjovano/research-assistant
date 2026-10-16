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
LEFT = 40.0
INDENT = 52.0
RIGHT = 500.0
LINE_HALF_HEIGHT = 6.0
FILE_PAGE = 1
SUBLEVEL = 2
LEAD_IN = "Reid names a kind of doubter whom no argument, however long, could ever hope to bring round:"
QUOTATION = "If a skeptic should build his skepticism upon this foundation, he must be left to enjoy it."
CITATION = "(1785: 480)"
FOLLOWING = "Does this mean that on Reid's view such total doubt cannot be answered, as some have held?"
LEAD_IN_BASELINE = 80.0
QUOTATION_BASELINE = 110.0
CITATION_BASELINE = 122.0
FOLLOWING_BASELINE = 150.0
LABEL = "Secondary Epistemic Seeing (SES)"
CONDITIONS = "(i) Maurice is angry; (ii) you see the crockery; (iii) conditions are such that it would not be broken."
LABEL_BASELINE = 80.0
CONDITIONS_BASELINE = 98.0
DRIFT = 3.5
NUMBERED_THESIS = "9. Noemata are not perceived through our senses."


@dataclass(frozen=True)
class CitationSetting:
    left: float
    font: str


class QuotationPagePdf:
    def __init__(self, path: Path, citation: CitationSetting) -> None:
        self._path = path
        self._citation = citation

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=RIGHT + LEFT)
            lines = [(LEFT, LEAD_IN_BASELINE, LEAD_IN, FONT), (INDENT, QUOTATION_BASELINE, QUOTATION, FONT),
                     (self._citation.left, CITATION_BASELINE, CITATION, self._citation.font),
                     (LEFT, FOLLOWING_BASELINE, FOLLOWING, FONT)]
            for left, baseline, text, font in lines:
                page.insert_text((left, baseline), text, fontsize=BODY_SIZE, fontname=font)
            document.save(self._path)
        return self._path


def line_box(left: float, baseline: float) -> tuple:
    return (left, baseline - BODY_SIZE - LINE_HALF_HEIGHT / 2, RIGHT, baseline + LINE_HALF_HEIGHT / 2)


def engine_reading(citation_left: float) -> list[Block]:
    return [BlockPlace(line_box(LEFT, LEAD_IN_BASELINE), 0).block(TEXT_KIND, f"<p>{LEAD_IN}</p>"),
            BlockPlace(line_box(INDENT, QUOTATION_BASELINE), 1).block(TEXT_KIND, f"<p>{QUOTATION}</p>"),
            BlockPlace(line_box(citation_left, CITATION_BASELINE), 2).block(HEADING_KIND, f"<h4>{CITATION}</h4>"),
            BlockPlace(line_box(LEFT, FOLLOWING_BASELINE), 3).block(TEXT_KIND, f"<p>{FOLLOWING}</p>")]


class LabelPagePdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=RIGHT + LEFT)
            for left, baseline, text in [(INDENT, LABEL_BASELINE, LABEL), (INDENT, CONDITIONS_BASELINE, CONDITIONS),
                                         (LEFT, FOLLOWING_BASELINE, FOLLOWING)]:
                page.insert_text((left, baseline), text, fontsize=BODY_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


def label_reading() -> list[Block]:
    return [BlockPlace(line_box(INDENT, LABEL_BASELINE), 0).block(HEADING_KIND, f"<h3>{LABEL}</h3>"),
            BlockPlace(line_box(INDENT, CONDITIONS_BASELINE), 1).block(TEXT_KIND, f"<p>{CONDITIONS}</p>"),
            BlockPlace(line_box(LEFT, FOLLOWING_BASELINE), 2).block(TEXT_KIND, f"<p>{FOLLOWING}</p>")]


class DriftingColumnPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=RIGHT + LEFT)
            for _kind, left, baseline, text in drifting_column():
                page.insert_text((left, baseline), text, fontsize=BODY_SIZE, fontname=FONT)
            document.save(self._path)
        return self._path


def drifting_column() -> list[tuple[str, float, float, str]]:
    drifted = LEFT + DRIFT
    return [(TEXT_KIND, LEFT, LEAD_IN_BASELINE, LEAD_IN), (TEXT_KIND, drifted, QUOTATION_BASELINE, QUOTATION),
            (HEADING_KIND, drifted, CITATION_BASELINE, NUMBERED_THESIS), (TEXT_KIND, drifted, FOLLOWING_BASELINE, FOLLOWING)]


def drifting_reading() -> list[Block]:
    return [BlockPlace(line_box(left, baseline), index).block(kind, f"<p>{text}</p>")
            for index, (kind, left, baseline, text) in enumerate(drifting_column())]


class TestBodyTypeLinesSetAtTheIndentOfADisplayedQuotation(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._directory = Path(directory.name)

    def _written(self, citation: CitationSetting) -> list[tuple[str, str]]:
        layer = TextLayer(QuotationPagePdf(self._directory / "quotation.pdf", citation).write())
        self.addCleanup(layer.close)
        page = PageBlocks(FILE_PAGE, engine_reading(citation.left))
        result = page_assembler(layer, keep_everything()).assemble(page, [], SUBLEVEL)
        return [(type(element).__name__, element.title if isinstance(element, Heading) else element.text)
                for element in result.elements if isinstance(element, (Heading, Paragraph))]

    def test_a_citation_line_closing_the_quotation_at_its_indent_is_written_as_a_line(self) -> None:
        self.assertIn((Paragraph.__name__, CITATION), self._written(CitationSetting(INDENT, FONT)))

    def test_a_body_type_line_at_the_column_edge_stays_a_heading(self) -> None:
        self.assertIn((Heading.__name__, CITATION), self._written(CitationSetting(LEFT, FONT)))

    def test_a_line_at_the_quotations_indent_in_a_type_apart_from_the_body_stays_a_heading(self) -> None:
        self.assertIn((Heading.__name__, CITATION), self._written(CitationSetting(INDENT, BOLD_FONT)))

    def test_a_label_line_opening_an_indented_display_at_its_indent_is_written_as_a_line(self) -> None:
        layer = TextLayer(LabelPagePdf(self._directory / "label.pdf").write())
        self.addCleanup(layer.close)
        result = page_assembler(layer, keep_everything()).assemble(PageBlocks(FILE_PAGE, label_reading()), [], SUBLEVEL)
        self.assertIn(Paragraph(LABEL, False, FILE_PAGE), result.elements)

    def test_a_body_type_line_where_the_columns_left_edge_drifts_by_less_than_an_indent_stays_a_heading(self) -> None:
        layer = TextLayer(DriftingColumnPdf(self._directory / "drifting.pdf").write())
        self.addCleanup(layer.close)
        page = PageBlocks(FILE_PAGE, drifting_reading())
        result = page_assembler(layer, keep_everything()).assemble(page, [], SUBLEVEL)
        self.assertIn(NUMBERED_THESIS, [element.title for element in result.elements if isinstance(element, Heading)])


if __name__ == "__main__":
    unittest.main()
