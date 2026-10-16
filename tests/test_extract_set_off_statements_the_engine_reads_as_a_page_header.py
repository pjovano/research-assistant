from __future__ import annotations

import shutil
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.blocks import HEADING_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.furniture import HEADER_KIND, WorkFurniture
from _extract.layer import TextLayer

LABEL = "Sensitivity"
STATEMENT_LINES = ["In order to constitute knowledge a belief", "must be sensitive."]
STATEMENT = " ".join(STATEMENT_LINES)
MASTHEAD = "PHILOSOPHICAL STUDIES VOL. 26, NO. 1"
CITATION = "Philosophical Studies 26 (1999), 373-392."
TITLE = "How Knowledge Relates to What Is Known"
BODY = "The sensitivity of a belief figures in requirements for correct attribution of knowledge."
FONT = "helv"
BODY_SIZE = 9.0
CITATION_SIZE = 6.0
LINE_HEIGHT = 11.0
LABEL_SPAN, STATEMENT_SPAN, BODY_SPAN = (118.0, 160.0), (190.0, 350.0), (82.0, 520.0)
HEAD_BASELINE = 88.0
TITLE_BASELINE = 115.0
BODY_BASELINE = 140.0
PAGES = 2


@dataclass(frozen=True)
class PrintedHeader:
    html: str
    span: tuple[float, float]
    size: float = BODY_SIZE

    @property
    def lines(self) -> list[str]:
        return self.html.split("<br/>")

    @property
    def box(self) -> tuple:
        return _box(self.span, HEAD_BASELINE, len(self.lines))


@dataclass(frozen=True)
class PrintedPage:
    headers: list[PrintedHeader]
    titled: bool = False


STATEMENT_PAGE = PrintedPage([PrintedHeader(LABEL, LABEL_SPAN), PrintedHeader("<br/>".join(STATEMENT_LINES),
                                                                               STATEMENT_SPAN)])
MASTHEAD_PAGE = PrintedPage([PrintedHeader(MASTHEAD, BODY_SPAN)])
SMALL_CITATION_PAGE = PrintedPage([PrintedHeader(CITATION, BODY_SPAN, CITATION_SIZE)])
TITLED_CITATION_PAGE = PrintedPage([PrintedHeader(CITATION, BODY_SPAN)], titled=True)


def _box(span: tuple[float, float], baseline: float, lines: int = 1) -> tuple:
    left, right = span
    return (left - 2.0, baseline - LINE_HEIGHT, right, baseline + (lines - 1) * LINE_HEIGHT + 3.0)


class StatementPagesPdf:
    def __init__(self, directory: Path) -> None:
        self._path = directory / "statement.pdf"

    def write(self, printed: PrintedPage, printed_pages: set[int]) -> Path:
        with pymupdf.open() as document:
            for file_page in range(1, PAGES + 1):
                page = document.new_page()
                self._line(page, (BODY_SPAN[0], BODY_BASELINE), BODY)
                if printed.titled:
                    self._line(page, (BODY_SPAN[0], TITLE_BASELINE), TITLE)
                for header in printed.headers if file_page in printed_pages else []:
                    self._header(page, header)
            document.save(self._path)
        return self._path

    def _header(self, page, header: PrintedHeader) -> None:
        for row, line in enumerate(header.lines):
            origin = (header.span[0], HEAD_BASELINE + row * LINE_HEIGHT)
            page.insert_text(origin, line, fontsize=header.size, fontname=FONT)

    @staticmethod
    def _line(page, origin: tuple[float, float], text: str) -> None:
        page.insert_text(origin, text, fontsize=BODY_SIZE, fontname=FONT)


def engine_reading(printed: PrintedPage, printed_pages: set[int]) -> DocumentBlocks:
    pages = []
    for file_page in range(1, PAGES + 1):
        headers = printed.headers if file_page in printed_pages else []
        blocks = [Block(file_page, HEADER_KIND, header.html, header.box, {}, f"/page/{file_page}/head/{index}")
                  for index, header in enumerate(headers)]
        if printed.titled:
            blocks.append(Block(file_page, HEADING_KIND, f"<h1>{TITLE}</h1>", _box(BODY_SPAN, TITLE_BASELINE), {},
                                f"/page/{file_page}/title"))
        blocks.append(Block(file_page, TEXT_KIND, f"<p>{BODY}</p>", _box(BODY_SPAN, BODY_BASELINE), {},
                            f"/page/{file_page}/body"))
        pages.append(PageBlocks(file_page, blocks))
    return DocumentBlocks(pages)


class TestSetOffStatementsTheEngineReadsAsAPageHeader(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def _headers(self, printed: PrintedPage, printed_pages: set[int]) -> list[Block]:
        layer = TextLayer(StatementPagesPdf(self._directory).write(printed, printed_pages))
        self.addCleanup(layer.close)
        refiled = WorkFurniture(layer).refiled(engine_reading(printed, printed_pages))
        return [block for page in refiled.pages for block in page.blocks
                if block.plain_text not in (BODY, TITLE)]

    def _kinds(self, printed: PrintedPage) -> dict[str, str]:
        return {block.plain_text: block.kind for block in self._headers(printed, {1})}

    def test_a_statement_printed_once_at_the_head_above_the_text_is_text(self) -> None:
        self.assertEqual(TEXT_KIND, self._kinds(STATEMENT_PAGE)[STATEMENT])

    def test_the_label_beside_the_statement_is_text(self) -> None:
        self.assertEqual(TEXT_KIND, self._kinds(STATEMENT_PAGE)[LABEL])

    def test_the_statement_reads_as_one_paragraph(self) -> None:
        statement = next(block for block in self._headers(STATEMENT_PAGE, {1}) if block.plain_text == STATEMENT)
        self.assertNotIn("<br", statement.html)

    def test_a_statement_repeated_on_every_page_stays_furniture(self) -> None:
        self.assertEqual({HEADER_KIND}, {block.kind for block in self._headers(STATEMENT_PAGE, {1, 2})})

    def test_a_masthead_printed_once_that_reads_as_no_sentence_stays_furniture(self) -> None:
        self.assertEqual({MASTHEAD: HEADER_KIND}, self._kinds(MASTHEAD_PAGE))

    def test_a_citation_set_smaller_than_the_text_stays_furniture(self) -> None:
        self.assertEqual({CITATION: HEADER_KIND}, self._kinds(SMALL_CITATION_PAGE))

    def test_a_citation_set_above_the_works_title_stays_furniture(self) -> None:
        self.assertEqual({CITATION: HEADER_KIND}, self._kinds(TITLED_CITATION_PAGE))


if __name__ == "__main__":
    unittest.main()
