from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _extract.cache import CachedConversions

FORCED_OCR_CACHE = "marker-forced-ocr-layout.json"
TEXT_LAYER_CACHE = "marker-text-layer-layout.json"
READ_PAGE = {"block_type": "Page", "children": [{"block_type": "Text", "html": "<p>read</p>"}]}
EMPTY_PAGE = {"block_type": "Page", "children": []}


class CachedConversionsCase(unittest.TestCase):
    def setUp(self) -> None:
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.scratch = Path(scratch.name)

    def cache(self, basename: str, name: str, pages: list[dict]) -> None:
        directory = self.scratch / basename
        directory.mkdir(exist_ok=True)
        entry = {"fingerprint": [], "pages": list(range(1, len(pages) + 1)), "payload": {"children": pages}}
        (directory / name).write_text(json.dumps(entry), encoding="utf-8")

    def listed(self) -> list[dict]:
        return CachedConversions(self.scratch).with_empty_pages()


class TestCachedConversionsWithEmptyPages(CachedConversionsCase):
    def test_a_conversion_whose_every_page_came_back_empty_is_listed_with_its_pages(self) -> None:
        self.cache("Blank - 2020 - Work", FORCED_OCR_CACHE, [EMPTY_PAGE, EMPTY_PAGE])
        listed = self.listed()
        self.assertEqual([("Blank - 2020 - Work", "forced-ocr", 2, [1, 2])],
                         [(item["basename"], item["mode"], item["pages"], item["empty_pages"]) for item in listed])

    def test_a_conversion_whose_every_page_holds_a_block_is_not_listed(self) -> None:
        self.cache("Read - 2020 - Work", TEXT_LAYER_CACHE, [READ_PAGE, READ_PAGE])
        self.assertEqual([], self.listed())

    def test_the_conversion_with_the_larger_share_of_empty_pages_comes_first(self) -> None:
        self.cache("One Blank - 2020 - Work", TEXT_LAYER_CACHE, [READ_PAGE, READ_PAGE, READ_PAGE, EMPTY_PAGE])
        self.cache("All Blank - 2020 - Work", FORCED_OCR_CACHE, [EMPTY_PAGE, EMPTY_PAGE])
        self.assertEqual(["All Blank - 2020 - Work", "One Blank - 2020 - Work"],
                         [item["basename"] for item in self.listed()])

    def test_an_unreadable_cache_file_is_not_listed(self) -> None:
        directory = self.scratch / "Torn - 2020 - Work"
        directory.mkdir()
        (directory / FORCED_OCR_CACHE).write_text("{", encoding="utf-8")
        self.assertEqual([], self.listed())

    def test_listing_writes_nothing(self) -> None:
        self.cache("Blank - 2020 - Work", FORCED_OCR_CACHE, [EMPTY_PAGE])
        before = sorted((path, path.stat().st_mtime_ns) for path in self.scratch.rglob("*"))
        self.listed()
        self.assertEqual(before, sorted((path, path.stat().st_mtime_ns) for path in self.scratch.rglob("*")))


if __name__ == "__main__":
    unittest.main()
