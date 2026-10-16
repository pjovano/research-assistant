from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest import mock

from _support import LiveTree

LiveTree.activate()

from _extract.build import ConversionOptions, ConversionPlan, PageConversion
from _extract.cache import MarkerCache
from _extract.engine import MODE_FORCED_OCR
from _vaults import LinedPdf, TempVault

BASENAME = "Doe - 2020 - A Work"
PAGES = [["The argument of the work runs on across this page,", "and the next line carries it further."]] * 3
ALL_PAGES = [1, 2, 3]
NOTATION_PAGES = [2, 3]
PAGE_BOX = [0, 0, 612, 792]
LATER_NANOSECONDS = 10**9


def page_payload(file_page: int) -> dict:
    return {"block_type": "Page", "id": f"/page/{file_page - 1}/Page/0", "bbox": PAGE_BOX, "children": []}


def payload_of(file_pages: list[int]) -> dict:
    return {"children": [page_payload(file_page) for file_page in file_pages]}


def page_ids(payload: dict) -> list[str]:
    return [page["id"] for page in payload["children"]]


class PagedEngine:
    def __init__(self) -> None:
        self.converted: list[list[int]] = []

    def convert(self, _pdf_path: Path, file_pages: list[int]) -> dict:
        self.converted.append(list(file_pages))
        return payload_of(file_pages)


class CachedWorkCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("LIBRARY_DIR").activate()
        self.addCleanup(self.vault.discard)
        self.pdf = LinedPdf(self.vault.library / f"{BASENAME}.pdf", PAGES).write()
        self.cache = MarkerCache(self.pdf, MODE_FORCED_OCR)
        self.engine = PagedEngine()

    def converted(self, file_pages: list[int]) -> dict:
        return PageConversion(self.pdf, self.engine, self.cache).payload(file_pages)


class TestAConversionOfPagesACachedConversionHolds(CachedWorkCase):
    def test_only_the_pages_the_cache_lacks_are_converted(self) -> None:
        self.cache.save(NOTATION_PAGES, payload_of(NOTATION_PAGES))
        self.converted(ALL_PAGES)
        self.assertEqual([[1]], self.engine.converted)

    def test_the_payload_holds_every_requested_page_in_order(self) -> None:
        self.cache.save(NOTATION_PAGES, payload_of(NOTATION_PAGES))
        self.assertEqual(page_ids(payload_of(ALL_PAGES)), page_ids(self.converted(ALL_PAGES)))

    def test_the_cache_holds_every_page_afterwards(self) -> None:
        self.cache.save(NOTATION_PAGES, payload_of(NOTATION_PAGES))
        self.converted(ALL_PAGES)
        self.assertTrue(self.cache.holds(ALL_PAGES))

    def test_pages_the_cache_wholly_holds_are_not_converted(self) -> None:
        self.cache.save(ALL_PAGES, payload_of(ALL_PAGES))
        self.converted(NOTATION_PAGES)
        self.assertEqual([], self.engine.converted)

    def test_a_cache_of_a_pdf_rewritten_since_holds_none_of_its_pages(self) -> None:
        self.cache.save(ALL_PAGES, payload_of(ALL_PAGES))
        stamp = self.pdf.stat().st_mtime_ns + LATER_NANOSECONDS
        os.utime(self.pdf, ns=(stamp, stamp))
        self.assertEqual(ALL_PAGES, self.cache.missing(ALL_PAGES))


class TestAConversionWithoutAPageEntryPerPage(CachedWorkCase):
    def test_it_is_served_for_its_own_pages(self) -> None:
        self.cache.save(ALL_PAGES, {"children": []})
        self.assertEqual({"children": []}, self.cache.load(ALL_PAGES))

    def test_it_holds_none_of_its_pages_alone(self) -> None:
        self.cache.save(ALL_PAGES, {"children": []})
        self.assertEqual([1], self.cache.missing([1]))


class TestAWorkReadFromPixelsAfterItsNotationPass(CachedWorkCase):
    def test_only_the_pages_outside_the_notation_pass_are_converted(self) -> None:
        self.cache.save(NOTATION_PAGES, payload_of(NOTATION_PAGES))
        with mock.patch("_extract.build.MarkerEngine", lambda _models, _mode: self.engine):
            ConversionPlan(self.pdf, ConversionOptions(force_ocr=True)).blocks(len(PAGES))
        self.assertEqual([[1]], self.engine.converted)


if __name__ == "__main__":
    unittest.main()
