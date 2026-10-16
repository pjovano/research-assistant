from __future__ import annotations

import contextlib
import io
import json
import unittest
from unittest import mock

from _support import LiveTree

LiveTree.activate()

from _extract.cache import MarkerCache
from _extract.cli import main
from _extract.engine import MODE_FORCED_OCR
from _extract.enginecost import FontRecord
from _extract.prefetch import SKIP_LAYER_UNSAMPLED, PrefetchConversion
from _extract.layersample import (
    LAYER_SAMPLE_MODE, MIN_NOTATION_SPANS, MIN_UNIT_PAGES, SAMPLES_PER_UNIT, LayerSampleReport, SampleUnits,
)
from _extract.scanlayer import READS_LAYER, READS_PIXELS, LayerCoverage
from _scan_layer_fixtures import (
    BASENAME, CHAPTER_PAGES, NOTATION_SPAN, PAGE_COUNT, ScanLayerCase, ScannedBook, misread_prose, page_prose,
)

FRONTMATTER = "---\ntitle: A Scanned Book\ntype: book\n---\n"

FORCE_OCR = "--force-ocr"
FORCE_OCR_PAGES = "--force-ocr-pages"
WHOLE_LAYER = LayerCoverage(PAGE_COUNT, PAGE_COUNT)
SECOND_CHAPTER = range(CHAPTER_PAGES + 1, PAGE_COUNT + 1)


def misread_in_the_second_chapter(file_page: int) -> str:
    return misread_prose(file_page) if file_page in SECOND_CHAPTER else page_prose(file_page)


def notation_in_the_second_chapter(file_page: int) -> str:
    notation = " ".join([NOTATION_SPAN] * MIN_NOTATION_SPANS) if file_page in SECOND_CHAPTER else ""
    return f"{page_prose(file_page)} {notation}"


class TestAScanWhoseLayerMatchesItsPixelReading(ScanLayerCase):
    def report(self, **sample) -> dict:
        layer_sample, _engine = self.sample(**sample)
        return LayerSampleReport(WHOLE_LAYER, layer_sample.sampled_units()).as_dict()

    def test_every_unit_whose_samples_match_reads_from_the_layer(self) -> None:
        self.assertEqual((READS_LAYER, []), (self.report()["reads"], self.report()["flags"]))

    def test_a_unit_whose_layer_misreads_its_words_is_read_from_pixels_whole(self) -> None:
        report = self.report(layer_prose=misread_in_the_second_chapter)
        self.assertEqual((READS_LAYER, [FORCE_OCR_PAGES, f"{SECOND_CHAPTER.start}-{PAGE_COUNT}"]),
                         (report["reads"], report["flags"]))

    def test_a_unit_whose_pixel_reading_carries_notation_is_read_from_pixels_whole(self) -> None:
        report = self.report(pixels=notation_in_the_second_chapter)
        self.assertEqual([FORCE_OCR_PAGES, f"{SECOND_CHAPTER.start}-{PAGE_COUNT}"], report["flags"])

    def test_a_scan_whose_every_unit_misreads_reads_every_page_from_pixels(self) -> None:
        report = self.report(layer_prose=misread_prose)
        self.assertEqual((READS_PIXELS, [FORCE_OCR], None), (report["reads"], report["flags"], report["pixel_pages"]))

    def test_each_unit_is_sampled_on_its_own_pages(self) -> None:
        layer_sample, _engine = self.sample()
        units = layer_sample.sampled_units()
        self.assertEqual([SAMPLES_PER_UNIT] * len(units), [len(unit.readings) for unit in units])
        self.assertTrue(all(reading.file_page in unit.pages for unit in units for reading in unit.readings))

    def test_the_samples_are_cached_apart_from_the_pixel_conversion_a_chapter_reads(self) -> None:
        layer_sample, _engine = self.sample()
        sampled = [reading.file_page for unit in layer_sample.sampled_units() for reading in unit.readings]
        pixel_cache, sample_cache = (MarkerCache(self.pdf_path, mode) for mode in (MODE_FORCED_OCR, LAYER_SAMPLE_MODE))
        self.assertEqual((sampled, []), (pixel_cache.missing(sampled), sample_cache.missing(sampled)))

    def test_a_second_sample_reads_its_pages_from_the_cache(self) -> None:
        layer_sample, engine = self.sample()
        layer_sample.sampled_units()
        layer_sample.sampled_units()
        self.assertEqual(1, len(engine.converted))


class TestPrefetchingAScan(ScanLayerCase):
    def conversion(self, state: dict) -> PrefetchConversion:
        ScannedBook(self.pdf_path).write()
        (self.vault.corpus / f"{BASENAME}.md").write_text(FRONTMATTER, encoding="utf-8")
        return PrefetchConversion(self.pdf_path.name, FontRecord(state))

    def test_a_scan_whose_layer_awaits_its_sample_is_skipped(self) -> None:
        self.assertEqual(SKIP_LAYER_UNSAMPLED, self.conversion({"fonts_checked": True}).skip_reason())

    def test_a_scan_whose_sample_reads_its_layer_is_converted(self) -> None:
        self.assertIsNone(self.conversion({"fonts_checked": True, "layer_sample": READS_LAYER}).skip_reason())


class TestAScanWhoseLayerIsTooThinToSample(ScanLayerCase):
    def test_it_reads_every_page_from_pixels_without_starting_the_engine(self) -> None:
        ScannedBook(self.pdf_path).write(pages_with_layer=PAGE_COUNT // 2)
        (self.vault.corpus / f"{BASENAME}.md").write_text(FRONTMATTER, encoding="utf-8")
        output = io.StringIO()
        with mock.patch("_extract.stage.EngineSession", side_effect=AssertionError("the engine started")), \
                contextlib.redirect_stdout(output):
            main(["layer-sample", self.pdf_path.name])
        report = json.loads(output.getvalue())
        self.assertEqual((READS_PIXELS, [FORCE_OCR], []), (report["reads"], report["flags"], report["units"]))

    def test_a_layer_on_four_pages_in_five_suffices(self) -> None:
        self.assertEqual((True, False), (LayerCoverage(8, 10).suffices, LayerCoverage(7, 10).suffices))


class TestTheUnitsAScanIsSampledIn(unittest.TestCase):
    def test_chapters_shorter_than_a_unit_join_the_chapters_after_them(self) -> None:
        chapters = [range(1, 6), range(6, 16), range(16, 30), range(30, 61)]
        self.assertEqual([range(1, 30), range(30, 61)], SampleUnits(chapters).units())

    def test_a_short_last_chapter_joins_the_unit_before_it(self) -> None:
        chapters = [range(1, MIN_UNIT_PAGES + 1), range(MIN_UNIT_PAGES + 1, MIN_UNIT_PAGES + 4)]
        self.assertEqual([range(1, MIN_UNIT_PAGES + 4)], SampleUnits(chapters).units())

    def test_a_work_shorter_than_a_unit_is_one_unit(self) -> None:
        self.assertEqual([range(1, 9)], SampleUnits([range(1, 4), range(4, 9)]).units())

    def test_every_unit_begins_where_a_chapter_begins(self) -> None:
        chapters = [range(1, 8), range(8, 31), range(31, 33), range(33, 70)]
        starts = {chapter.start for chapter in chapters}
        self.assertTrue(all(unit.start in starts for unit in SampleUnits(chapters).units()))


if __name__ == "__main__":
    unittest.main()
