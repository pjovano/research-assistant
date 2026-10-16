from __future__ import annotations

import contextlib
import io
import json
import unicodedata
import unittest

from _support import LiveTree

LiveTree.activate()

import vault
from _vaults import TempVault

REVIEWED = "Doe - 2020 - A Work"
UNREVIEWED = "Roe - 2021 - Another Work"
UNRECORDED = "Poe - 2022 - A Third Work"
LAYOUT_ONLY = "Moe - 2019 - A Layout Work"
ENGINE_LAYOUT = "marker-text-layer-layout.json"
REVIEW_DATE = "2026-10-01"
RENDER_BYTES = b"0123456789"
CACHE_BYTES = b"{}"
ENTRIES_PER_FILLED_CACHE = 6


class ReviewedSweepCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("LIBRARY_DIR", "VOLUMES_DIR", "INBOX_DIR").activate()
        self.addCleanup(self.vault.discard)
        self.scratch = vault.SCRATCH_DIR
        self.write_records({REVIEWED: {vault.REVIEWED_KEY: REVIEW_DATE}, UNREVIEWED: {},
                            LAYOUT_ONLY: {vault.REVIEWED_KEY: REVIEW_DATE}})
        for name in (REVIEWED, UNREVIEWED, UNRECORDED):
            self.fill_work_cache(name)
        (self.scratch / LAYOUT_ONLY).mkdir()
        (self.scratch / LAYOUT_ONLY / ENGINE_LAYOUT).write_bytes(CACHE_BYTES)

    def write_records(self, records: dict) -> None:
        (self.vault.library / vault.RECORDS_FILE_NAME).write_text(json.dumps(records), encoding="utf-8")

    def fill_work_cache(self, name: str) -> None:
        work = self.scratch / name
        (work / vault.GLYPHS_DIRECTORY).mkdir(parents=True)
        (work / vault.GLYPHS_DIRECTORY / "code-0041.png").write_bytes(RENDER_BYTES)
        (work / vault.RENDER_NAME.format(number=1)).write_bytes(RENDER_BYTES)
        (work / vault.RENDER_NAME.format(number=2)).write_bytes(RENDER_BYTES)
        (work / vault.PIXELS_CACHE_NAME).write_bytes(CACHE_BYTES)
        (work / vault.OCCURRENCES_CACHE_NAME).write_bytes(CACHE_BYTES)
        (work / ENGINE_LAYOUT).write_bytes(CACHE_BYTES)

    def listed(self, *flags: str) -> list[dict]:
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            vault.VaultCommandLine().run(["sweep", "--reviewed", *flags])
        return json.loads(printed.getvalue())["rebuildable"]

    def listed_names(self) -> list[str]:
        return [entry["entry"] for entry in self.listed()]

    def remaining(self, name: str) -> list[str]:
        return sorted(path.name for path in (self.scratch / name).iterdir())


class TestTheReviewedSweepListsTheRebuildableCachesOfReviewedWorks(ReviewedSweepCase):
    def test_only_a_reviewed_work_with_renders_or_font_repair_caches_is_listed(self) -> None:
        self.assertEqual([REVIEWED], self.listed_names())

    def test_a_listed_work_reports_the_size_of_its_renders_and_font_repair_caches_alone(self) -> None:
        rebuildable_bytes = 3 * len(RENDER_BYTES) + 2 * len(CACHE_BYTES)
        self.assertEqual(rebuildable_bytes, self.listed()[0]["bytes"])

    def test_a_record_keyed_by_a_decomposed_basename_names_the_composed_cache(self) -> None:
        composed = "Fré - 2018 - A Work"
        self.write_records({unicodedata.normalize("NFD", composed): {vault.REVIEWED_KEY: REVIEW_DATE}})
        self.fill_work_cache(composed)
        self.assertEqual([composed], self.listed_names())

    def test_without_an_extraction_records_file_nothing_is_listed(self) -> None:
        (self.vault.library / vault.RECORDS_FILE_NAME).unlink()
        self.assertEqual([], self.listed_names())

    def test_an_unreadable_extraction_records_file_fails_naming_the_file(self) -> None:
        (self.vault.library / vault.RECORDS_FILE_NAME).write_text("{", encoding="utf-8")
        with self.assertRaises(vault.ExtractionRecordsUnreadable) as raised:
            self.listed()
        self.assertIn(vault.RECORDS_FILE_NAME, str(raised.exception))

    def test_the_listing_deletes_nothing(self) -> None:
        self.listed()
        self.assertIn(vault.RENDER_NAME.format(number=1), self.remaining(REVIEWED))


class TestTheReviewedSweepApplyDeletesOnlyTheRebuildableCaches(ReviewedSweepCase):
    def setUp(self) -> None:
        super().setUp()
        self.listed("--apply")

    def test_a_reviewed_work_keeps_its_engine_layout_alone(self) -> None:
        self.assertEqual([ENGINE_LAYOUT], self.remaining(REVIEWED))

    def test_a_work_without_a_reviewed_date_keeps_every_cache(self) -> None:
        for name in (UNREVIEWED, UNRECORDED):
            with self.subTest(name=name):
                self.assertEqual(ENTRIES_PER_FILLED_CACHE, len(self.remaining(name)))

    def test_a_second_sweep_finds_nothing(self) -> None:
        self.assertEqual([], self.listed_names())


if __name__ == "__main__":
    unittest.main()
