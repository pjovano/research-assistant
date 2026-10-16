from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import time
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

import vault
from _drive.runlock import RunHolder, RunLock

from _extract.backfill import BackfillCommands
from _extract.enginecost import (
    TEXT_PAGES_PER_PIXEL_PAGE,
    UNKNOWN_COST,
    CheapestFirst,
    EngineCost,
    EngineCosts,
    FontRecord,
    PdfReading,
)
from _layer_pdfs import RemappedPagesPdf, StandIn
from _vaults import TempVault

LONG_BOOK = "Long - 2001 - A Book of Prose.pdf"
NOTATION_ARTICLE = "Short - 2002 - An Article with Notation.pdf"
SCAN = "Scan - 1950 - A Scanned Work.pdf"
LONG_BOOK_PAGES = 30
SCAN_PAGES = 4
ARROW_CODE = "~"
PROSE_LINE = "The argument runs on in plain prose across the page."
PROSE_PAGE = [PROSE_LINE] * 4
NOTATION_LINE = "so p ~ q ~ r ~ s ~ t ~ u holds"
DRAWN_BOX = pymupdf.Rect(72, 72, 300, 300)


def prose_pdf(path: Path, pages: int) -> Path:
    return RemappedPagesPdf(path, [PROSE_PAGE] * pages, {}, [("One", 1)]).write()


def scanned_pdf(path: Path, pages: int) -> Path:
    with pymupdf.open() as document:
        for _ in range(pages):
            document.new_page().draw_rect(DRAWN_BOX, fill=(0.5, 0.5, 0.5))
        document.save(path)
    return path


class CountingReading:
    def __init__(self) -> None:
        self.reads = 0

    def __call__(self, pdf_path: Path) -> PdfReading:
        self.reads += 1
        return PdfReading.of(pdf_path)


class LibraryCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("LIBRARY_DIR").activate()
        self.addCleanup(self.vault.discard)
        prose_pdf(self.vault.library / LONG_BOOK, LONG_BOOK_PAGES)
        RemappedPagesPdf(self.vault.library / NOTATION_ARTICLE, [PROSE_PAGE, [*PROSE_PAGE, NOTATION_LINE]],
                         {ARROW_CODE: StandIn("→")}, [("One", 1)]).write()
        scanned_pdf(self.vault.library / SCAN, SCAN_PAGES)
        self.backfill = vault.SCRATCH_DIR / "backfill"

    def cost(self, pdf: str, state: dict | None = None) -> EngineCost:
        return EngineCosts().of(self.vault.library / pdf, FontRecord(state or {}))


class TestTheEngineCostOfAWork(LibraryCase):
    def test_a_text_layer_work_costs_no_pixel_page(self) -> None:
        self.assertEqual(EngineCost(0, LONG_BOOK_PAGES), self.cost(LONG_BOOK))

    def test_a_notation_page_is_a_pixel_page(self) -> None:
        self.assertEqual(EngineCost(1, 2), self.cost(NOTATION_ARTICLE))

    def test_a_work_with_no_text_layer_costs_every_page_from_pixels(self) -> None:
        self.assertEqual(EngineCost(SCAN_PAGES, SCAN_PAGES), self.cost(SCAN))

    def test_a_recorded_reading_from_pixels_costs_every_page(self) -> None:
        self.assertEqual(EngineCost(LONG_BOOK_PAGES, LONG_BOOK_PAGES), self.cost(LONG_BOOK, {"pixels_only": True}))

    def test_recorded_pixel_pages_add_to_the_notation_pages(self) -> None:
        self.assertEqual(EngineCost(3, 2), self.cost(NOTATION_ARTICLE, {"pixel_pages": "1-2,5"}))

    def test_a_scan_whose_sample_reads_its_layer_costs_only_the_pages_it_reads_from_pixels(self) -> None:
        self.assertEqual(EngineCost(2, SCAN_PAGES), self.cost(SCAN, {"layer_sample": "layer", "pixel_pages": "3-4"}))

    def test_a_scan_whose_sample_reads_pixels_costs_every_page(self) -> None:
        self.assertEqual(EngineCost(SCAN_PAGES, SCAN_PAGES), self.cost(SCAN, {"layer_sample": "pixels"}))


class TestTheEngineCostWeighsPixelPagesAgainstPages(unittest.TestCase):
    def test_a_pixel_page_weighs_as_many_text_pages(self) -> None:
        self.assertEqual(TEXT_PAGES_PER_PIXEL_PAGE + 9, EngineCost(1, 10).engine_time)

    def test_a_long_text_layer_book_costs_more_than_a_short_work_with_a_few_pixel_pages(self) -> None:
        self.assertLess(EngineCost(2, 40), EngineCost(0, 3 * TEXT_PAGES_PER_PIXEL_PAGE))

    def test_works_of_one_engine_time_rank_by_their_pages(self) -> None:
        self.assertLess(EngineCost(1, 1), EngineCost(0, TEXT_PAGES_PER_PIXEL_PAGE))

    def test_a_work_of_unknown_cost_ranks_after_every_known_cost(self) -> None:
        self.assertLess(EngineCost(1000, 1000), UNKNOWN_COST)


class TestTheEngineCostCache(LibraryCase):
    def test_a_pdf_is_read_once_while_it_stands(self) -> None:
        reading = CountingReading()
        for _ in range(2):
            EngineCosts(read=reading).of(self.vault.library / LONG_BOOK, FontRecord({}))
        self.assertEqual(1, reading.reads)

    def test_a_rewritten_pdf_is_read_again(self) -> None:
        reading = CountingReading()
        EngineCosts(read=reading).of(self.vault.library / LONG_BOOK, FontRecord({}))
        time.sleep(0.01)
        prose_pdf(self.vault.library / LONG_BOOK, LONG_BOOK_PAGES + 1)
        cost = EngineCosts(read=reading).of(self.vault.library / LONG_BOOK, FontRecord({}))
        self.assertEqual((2, EngineCost(0, LONG_BOOK_PAGES + 1)), (reading.reads, cost))


class TestTheBackfillQueueRankedCheapestFirst(LibraryCase):
    def commands(self) -> BackfillCommands:
        lock = RunLock(vault.SCRATCH_DIR / "ingest-run.json")
        return BackfillCommands(self.backfill, order=CheapestFirst.for_backfill(self.backfill), run_lock=lock)

    def queue_line(self) -> dict:
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            self.commands().queue(argparse.Namespace())
        return json.loads(printed.getvalue())

    def queued(self) -> list[str]:
        self.queue_line()
        return (self.backfill / "queue.txt").read_text(encoding="utf-8").splitlines()

    def test_a_long_text_layer_book_is_queued_before_a_short_work_with_a_notation_page(self) -> None:
        self.assertEqual([LONG_BOOK, NOTATION_ARTICLE, SCAN], self.queued())

    def test_a_held_run_lock_refuses_the_rewrite(self) -> None:
        RunLock(vault.SCRATCH_DIR / "ingest-run.json").take(RunHolder(os.getppid(), "extract", time.time()))
        line = self.queue_line()
        self.assertEqual(("halt", False), (line["state"], (self.backfill / "queue.txt").exists()))


class TestTheCostsCommandLine(LibraryCase):
    def test_each_pdf_is_listed_with_its_cost_and_an_unopened_one_with_none(self) -> None:
        order = CheapestFirst.for_backfill(self.backfill)
        listed = {pdf: order.cost(pdf).as_list() for pdf in (NOTATION_ARTICLE, "Absent - 2000 - Gone.pdf")}
        self.assertEqual({NOTATION_ARTICLE: [101, 2], "Absent - 2000 - Gone.pdf": None}, json.loads(json.dumps(listed)))


if __name__ == "__main__":
    unittest.main()
