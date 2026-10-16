from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

import pymupdf

from _support import LiveTree

LiveTree.activate()

import references
import vault
from _pagetext import quotes
from _vaults import TempVault
from scratch_cache import CACHE_NOT_WRITTEN

TEXT_ORIGIN = (72, 72)
PAGES = ["Chapter One\n\nSome body text about Kant and mathematics.",
         "References\n\nAllison, H. (1973). The Kant-Eberhard Controversy. Baltimore: Hopkins."]
CORRUPT_TEXT = '{"fingerprint": [1, 2'
BASENAME = "Some - 2005 - Work"


class ScratchCacheTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("LIBRARY_DIR").activate()
        self.addCleanup(self.vault.discard)
        self.pdf = self.vault.library / f"{BASENAME}.pdf"
        document = pymupdf.open()
        for text in PAGES:
            document.new_page().insert_text(TEXT_ORIGIN, text)
        document.save(self.pdf)
        document.close()

    def zone_cache(self):
        return vault.SCRATCH_DIR / BASENAME / references.ZONE_CACHE_NAME

    def page_cache(self):
        return vault.SCRATCH_DIR / BASENAME / quotes.CACHE_NAME

    def block_the_cache_directory(self) -> None:
        vault.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
        (vault.SCRATCH_DIR / BASENAME).write_text("a file where the cache directory goes", encoding="utf-8")


class TestACorruptZoneCacheIsRebuilt(ScratchCacheTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.zone_cache().parent.mkdir(parents=True)
        self.zone_cache().write_text(CORRUPT_TEXT, encoding="utf-8")

    def test_a_corrupt_zone_cache_is_read_as_absent_and_the_zone_located(self) -> None:
        self.assertEqual(references.ZoneLocator(self.pdf).locate(), references.CachedZone(self.pdf).locate())

    def test_a_corrupt_zone_cache_is_replaced_by_a_readable_one(self) -> None:
        located = references.CachedZone(self.pdf).locate()
        self.assertEqual(located, references.ZoneCache(self.pdf).loaded())

    def test_a_zone_cache_holding_no_zone_is_read_as_absent(self) -> None:
        references.CachedZone(self.pdf).locate()
        self.zone_cache().write_text('{"fingerprint": null, "zone": {"method": "x"}}', encoding="utf-8")
        self.assertIsNone(references.ZoneCache(self.pdf).loaded())


class TestACacheThatCannotBeWrittenIsReported(ScratchCacheTestCase):
    def test_a_zone_cache_that_cannot_be_written_is_reported_and_the_zone_still_located(self) -> None:
        self.block_the_cache_directory()
        with redirect_stderr(io.StringIO()) as reported:
            zone = references.CachedZone(self.pdf).locate()
        self.assertEqual((True, True), (zone.is_present, reported.getvalue().startswith(CACHE_NOT_WRITTEN)))

    def test_a_page_cache_that_cannot_be_written_is_reported(self) -> None:
        self.block_the_cache_directory()
        with redirect_stderr(io.StringIO()) as reported:
            quotes._NormalizedPages().of(self.pdf)
        self.assertTrue(reported.getvalue().startswith(CACHE_NOT_WRITTEN))


class TestACacheWriteKilledBeforeTheReplaceLeavesTheEarlierCacheWhole(ScratchCacheTestCase):
    def test_the_earlier_zone_cache_survives_a_write_killed_before_the_replace(self) -> None:
        references.CachedZone(self.pdf).locate()
        earlier = self.zone_cache().read_bytes()
        with patch.object(vault.ReplacementFile, "commit", side_effect=OSError("killed")), \
                redirect_stderr(io.StringIO()):
            references.ZoneCache(self.pdf).save(references.ReferenceZone(references.ABSENT, 0, 0, ""))
        self.assertEqual(earlier, self.zone_cache().read_bytes())

    def test_a_write_killed_before_the_replace_leaves_no_partial_file(self) -> None:
        with patch.object(vault.ReplacementFile, "commit", side_effect=OSError("killed")), \
                redirect_stderr(io.StringIO()):
            quotes._NormalizedPages().of(self.pdf)
        self.assertEqual([], list(self.page_cache().parent.iterdir()))


if __name__ == "__main__":
    unittest.main()
