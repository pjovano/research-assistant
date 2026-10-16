from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import BlockPlace
from _extract.blocks import FOOTER_KIND, HEADING_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.furniture import WorkFurniture
from _extract.layer import TextLayer
from _extract.pagefolios import FolioReader

HEADER_BASELINE = 50.0
FIRST_BODY_BASELINE = 80.0
LINE_PITCH = 14.0
LEFT = 72.0
RUNNING_HEAD_LEFT = 105.0
FONT_SIZE = 10.0
HEADER_KIND = "PageHeader"
HEADER_BOX = (70.0, 38.0, 500.0, 54.0)
MERGED_BOX = (70.0, 38.0, 500.0, 140.0)
BODY_BOX = (70.0, 66.0, 500.0, 140.0)
BODY_LINES = ["The concept is prior to judgment with respect to content, and",
              "the forms of judgment display that content in a new form."]
RUNNING_HEAD = "journal of the history of tests 61:1 january 2023"


class PagedPdf:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._pages: list[list[tuple]] = []

    def page(self, lines: list[tuple]) -> PagedPdf:
        self._pages.append(lines)
        return self

    def write(self) -> Path:
        with pymupdf.open() as document:
            for lines in self._pages:
                page = document.new_page()
                for baseline, text, *left in lines:
                    page.insert_text((left[0] if left else LEFT, baseline), text, fontname="helv", fontsize=FONT_SIZE)
            document.save(self._path)
        return self._path


def body_lines(first_baseline: float = FIRST_BODY_BASELINE) -> list[tuple[float, str]]:
    return [(first_baseline + row * LINE_PITCH, text) for row, text in enumerate(BODY_LINES)]


def block(kind: str, text: str, place: BlockPlace) -> Block:
    return place.block(kind, f"<p>{text}</p>")


class FurnitureCase(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def layer(self, pdf: PagedPdf) -> TextLayer:
        layer = TextLayer(pdf.write())
        self.addCleanup(layer.close)
        return layer

    def pdf(self) -> PagedPdf:
        return PagedPdf(self._directory / "furniture.pdf")


class TestRunningHeadMergedIntoTheText(FurnitureCase):
    def setUp(self) -> None:
        super().setUp()
        pdf = self.pdf()
        for folio in (122, 123):
            pdf.page([(HEADER_BASELINE, str(folio)), (HEADER_BASELINE, RUNNING_HEAD, RUNNING_HEAD_LEFT)] + body_lines())
        self.layer_pdf = self.layer(pdf)
        self.blocks = DocumentBlocks([
            PageBlocks(1, [block(HEADER_KIND, f"122 {RUNNING_HEAD}", BlockPlace(HEADER_BOX, 0, 1)),
                           block(TEXT_KIND, " ".join(BODY_LINES), BlockPlace(BODY_BOX, 1, 1))]),
            PageBlocks(2, [block(TEXT_KIND, f"123 {RUNNING_HEAD} " + " ".join(BODY_LINES),
                                 BlockPlace(MERGED_BOX, 0, 2))]),
        ])

    def test_a_running_head_the_engine_merged_into_the_text_below_is_furniture(self) -> None:
        page = WorkFurniture(self.layer_pdf).refiled(self.blocks).pages[1]
        self.assertEqual([f"123 {RUNNING_HEAD}"], page.furniture_texts)

    def test_the_text_below_a_merged_running_head_no_longer_holds_it(self) -> None:
        page = WorkFurniture(self.layer_pdf).refiled(self.blocks).pages[1]
        text = page.content[0]
        self.assertGreater(text.bbox.top, HEADER_BASELINE)

    def test_the_folio_of_a_merged_running_head_is_read(self) -> None:
        refiled = WorkFurniture(self.layer_pdf).refiled(self.blocks)
        self.assertEqual("123", FolioReader(self.layer_pdf).of(refiled.pages)[2])


class TestLineOfTheTextReadAsAFooter(FurnitureCase):
    def setUp(self) -> None:
        super().setUp()
        closing = FIRST_BODY_BASELINE + len(BODY_LINES) * LINE_PITCH
        pdf = self.pdf().page(body_lines() + [(closing, "larity. (W 5: 172)")])
        self.layer_pdf = self.layer(pdf)
        self.footer_box = (70.0, closing - FONT_SIZE, 180.0, closing + 2.0)
        self.text_box = (70.0, 66.0, 500.0, closing + 3.0)

    def refiled_kinds(self, footer_text: str) -> list[str]:
        page = PageBlocks(1, [block(TEXT_KIND, " ".join(BODY_LINES), BlockPlace(self.text_box, 0, 1)),
                              block(FOOTER_KIND, footer_text, BlockPlace(self.footer_box, 1, 1))])
        return [kept.kind for kept in WorkFurniture(self.layer_pdf).refiled(DocumentBlocks([page])).pages[0].blocks]

    def test_a_footer_the_work_prints_once_inside_the_text_is_a_line_of_the_text(self) -> None:
        self.assertEqual([TEXT_KIND], self.refiled_kinds("larity. (W 5: 172)"))

    def test_a_one_off_header_inside_a_heading_block_stays_furniture(self) -> None:
        page = PageBlocks(1, [block(HEADING_KIND, "", BlockPlace(self.footer_box, 0, 1)),
                              block(FOOTER_KIND, "CHAPTER THIRTY", BlockPlace(self.footer_box, 1, 1))])
        refiled = WorkFurniture(self.layer_pdf).refiled(DocumentBlocks([page])).pages[0].blocks
        self.assertEqual([HEADING_KIND, FOOTER_KIND], [kept.kind for kept in refiled])

    def test_a_folio_inside_the_text_stays_furniture(self) -> None:
        self.assertEqual([TEXT_KIND, FOOTER_KIND], self.refiled_kinds("172"))


if __name__ == "__main__":
    unittest.main()
