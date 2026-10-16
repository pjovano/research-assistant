from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _clean.outline import Outline as CleanOutline
from _clean.toc import TocDocument
from _extract.outline import PAGE_TOP
from _extract.outline import Outline as ExtractOutline

PAGE_WIDTH = 612.0
PAGE_HEIGHT = 792.0
MEDIA_BOX_OFF_THE_ORIGIN = pymupdf.Rect(0.0, 100.0, 612.0, 892.0)
CROP_BOX_INSIDE_THE_MEDIA_BOX = pymupdf.Rect(30.0, 20.0, 580.0, 700.0)
CROP_BOX_TOP_LEFT = (30.0, 872.0)
PLAIN_PAGE_TOP_LEFT = (0.0, PAGE_HEIGHT)
VISIBLE_TOP_LEFT_BY_ROTATION = {90: (0.0, 0.0), 180: (PAGE_WIDTH, 0.0), 270: (PAGE_WIDTH, PAGE_HEIGHT)}
ENTRY_TITLE = "Section One"
XYZ_RE = re.compile(r"/XYZ\s+(\S+)\s+(\S+)")


class OutlinedPdf:
    def __init__(self, directory: str) -> None:
        self._path = Path(directory) / "outlined.pdf"
        self._media_box: pymupdf.Rect | None = None
        self._crop_box: pymupdf.Rect | None = None
        self._rotation = 0

    def with_boxes(self, media_box: pymupdf.Rect, crop_box: pymupdf.Rect) -> "OutlinedPdf":
        self._media_box, self._crop_box = media_box, crop_box
        return self

    def rotated(self, rotation: int) -> "OutlinedPdf":
        self._rotation = rotation
        return self

    def written(self) -> Path:
        self._blank()
        TocDocument(self._path).write(CleanOutline.from_toc([[1, ENTRY_TITLE, 1]]))
        return self._path

    def _blank(self) -> None:
        with pymupdf.open() as doc:
            self._shape(doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT))
            doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            doc.save(self._path)

    def _shape(self, page: pymupdf.Page) -> None:
        if self._media_box is not None:
            page.set_mediabox(self._media_box)
            page.set_cropbox(self._crop_box)
        page.set_rotation(self._rotation)


class WrittenDestination:
    def __init__(self, path: Path) -> None:
        self._path = path

    def top_left(self) -> tuple[float, float]:
        with pymupdf.open(self._path) as doc:
            target = doc.xref_get_key(self._first_entry(doc), "A/D")[1]
        left, top = XYZ_RE.search(target).groups()
        return float(left), float(top)

    @staticmethod
    def _first_entry(doc: pymupdf.Document) -> int:
        outlines = doc.xref_get_key(doc.pdf_catalog(), "Outlines")[1]
        return int(doc.xref_get_key(int(outlines.split()[0]), "First")[1].split()[0])


class TestOutlineEntriesOpenAtTheTopLeftOfTheirVisiblePage(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)

    def _pdf(self) -> OutlinedPdf:
        return OutlinedPdf(self._directory.name)

    def test_an_entry_on_a_plain_page_opens_at_the_page_top_not_its_foot(self) -> None:
        self.assertEqual(PLAIN_PAGE_TOP_LEFT, WrittenDestination(self._pdf().written()).top_left())

    def test_an_entry_on_a_page_whose_crop_box_sits_off_the_origin_opens_at_the_crop_box_top(self) -> None:
        path = self._pdf().with_boxes(MEDIA_BOX_OFF_THE_ORIGIN, CROP_BOX_INSIDE_THE_MEDIA_BOX).written()
        self.assertEqual(CROP_BOX_TOP_LEFT, WrittenDestination(path).top_left())

    def test_an_entry_on_a_rotated_page_opens_at_the_top_left_the_page_shows(self) -> None:
        for rotation, top_left in VISIBLE_TOP_LEFT_BY_ROTATION.items():
            with self.subTest(rotation=rotation):
                path = self._pdf().rotated(rotation).written()
                self.assertEqual(top_left, WrittenDestination(path).top_left())

    def test_extraction_reads_a_written_entry_on_a_rotated_offset_page_at_the_page_top(self) -> None:
        for rotation in VISIBLE_TOP_LEFT_BY_ROTATION:
            with self.subTest(rotation=rotation):
                pdf = self._pdf().with_boxes(MEDIA_BOX_OFF_THE_ORIGIN, CROP_BOX_INSIDE_THE_MEDIA_BOX)
                path = pdf.rotated(rotation).written()
                self.assertEqual(PAGE_TOP, ExtractOutline(path).headings()[0].position)


if __name__ == "__main__":
    unittest.main()
