from __future__ import annotations

import os
import unittest

from _support import LiveTree

LiveTree.activate()

from conversion_cache_keys import CachedConversionsKept

from _clean.outline import Outline
from _clean.toc import TocDocument
from _extract.cache import MarkerCache
from _extract.engine import MODE_FORCED_OCR, MODE_TEXT_LAYER
from _vaults import LinedPdf, TempVault

BASENAME = "Doe - 2020 - A Work"
PAGES = [["The argument of the work runs on across this page,", "and the next line carries it further."]] * 3
ALL_PAGES = [1, 2, 3]
LATER_NANOSECONDS = 10**9


def payload_of(file_pages: list[int]) -> dict:
    return {"children": [{"block_type": "Page", "id": f"/page/{page - 1}/Page/0", "children": []}
                         for page in file_pages]}


class CachedWorkCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("LIBRARY_DIR").activate()
        self.addCleanup(self.vault.discard)
        self.pdf = LinedPdf(self.vault.library / f"{BASENAME}.pdf", PAGES).write()

    def cached(self, mode: str) -> MarkerCache:
        cache = MarkerCache(self.pdf, mode)
        cache.save(ALL_PAGES, payload_of(ALL_PAGES))
        return cache

    def touch_later(self) -> None:
        stamp = self.pdf.stat().st_mtime_ns + LATER_NANOSECONDS
        os.utime(self.pdf, ns=(stamp, stamp))


class TestAnOutlineWrittenIntoAPdfWithACachedConversion(CachedWorkCase):
    def test_the_cached_conversion_still_holds_every_page(self) -> None:
        cache = self.cached(MODE_TEXT_LAYER)
        TocDocument(self.pdf).write(Outline.from_toc([[1, "Introduction", 1]]))
        self.assertTrue(cache.holds(ALL_PAGES))

    def test_the_cached_conversion_of_every_mode_still_holds_every_page(self) -> None:
        caches = [self.cached(MODE_TEXT_LAYER), self.cached(MODE_FORCED_OCR)]
        TocDocument(self.pdf).write(Outline.from_toc([[1, "Introduction", 1]]))
        self.assertEqual([True, True], [cache.holds(ALL_PAGES) for cache in caches])


class TestAPageKeepingWrite(CachedWorkCase):
    def test_a_conversion_already_stale_before_the_write_stays_stale(self) -> None:
        cache = self.cached(MODE_TEXT_LAYER)
        self.touch_later()
        with CachedConversionsKept(self.pdf):
            self.touch_later()
        self.assertFalse(cache.holds(ALL_PAGES))

    def test_a_write_that_fails_rekeys_nothing(self) -> None:
        cache = self.cached(MODE_TEXT_LAYER)
        with self.assertRaises(RuntimeError), CachedConversionsKept(self.pdf):
            self.touch_later()
            raise RuntimeError("the write failed")
        self.assertFalse(cache.holds(ALL_PAGES))


if __name__ == "__main__":
    unittest.main()
