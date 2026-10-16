from __future__ import annotations

import json
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import pymupdf
import vault
from _clean.commands import TocCommands
from _clean.fontfilter import FilterError, FontFilter, FontReport, OutlineSuggestion
from _font_fixtures import SilentCommand
from _vaults import PATCHED_DIRS, TempVault

BODY = ("helv", 10)
CHAPTER = ("hebo", 16)
SECTION = ("hebo", 12)
LEFT = 72
LINE_HEIGHT = 14
MIXED_OFFSET = 60
MIXED_ROW = 6
CHAPTER_FILTER = "Helvetica-Bold:16:1"
SECTION_FILTER = "Helvetica-Bold:12:2"


class StyledPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as doc:
            self._first_page(doc.new_page())
            self._second_page(doc.new_page())
            self._third_page(doc.new_page())
            doc.save(self._path)
        return self._path

    def _first_page(self, page: pymupdf.Page) -> None:
        self._lines(page, [(CHAPTER, "Chapter One"), (BODY, "Body text of the opening."),
                           (SECTION, "1.1 First Section"), (BODY, "More body text.")])

    def _second_page(self, page: pymupdf.Page) -> None:
        self._lines(page, [(BODY, "Body continues."), (CHAPTER, "Chapter Two: A Title"),
                           (CHAPTER, "Wrapped Over Two Lines"), (BODY, "Body again.")])

    def _third_page(self, page: pymupdf.Page) -> None:
        self._lines(page, [(SECTION, "2.1 Second Section"), (BODY, "Body."), (SECTION, "2.2 Third Section")])
        writer = pymupdf.TextWriter(page.rect)
        writer.append((LEFT, LINE_HEIGHT * MIXED_ROW), "Mixed ", font=pymupdf.Font(CHAPTER[0]), fontsize=CHAPTER[1])
        writer.append((LEFT + MIXED_OFFSET, LINE_HEIGHT * MIXED_ROW), "fonts", font=pymupdf.Font(BODY[0]),
                      fontsize=CHAPTER[1])
        writer.write_text(page)

    def _lines(self, page: pymupdf.Page, rows: list[tuple[tuple[str, int], str]]) -> None:
        for index, ((font, size), text) in enumerate(rows, start=1):
            page.insert_text((LEFT, LINE_HEIGHT * index), text, fontname=font, fontsize=size)


class SuggestTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault(*PATCHED_DIRS).activate()
        self.addCleanup(self.vault.discard)
        self.pdf_path = StyledPdf(self.vault.inbox / "styled.pdf").write()

    def filters(self, *specs: str) -> list[FontFilter]:
        return [FontFilter.parsed(spec) for spec in specs]

    def suggested(self, *specs: str) -> list[dict]:
        return OutlineSuggestion(self.pdf_path, self.filters(*specs)).outline().as_dicts()


class TestFontReport(SuggestTestCase):
    def test_every_distinct_face_on_the_page_is_listed_with_a_sample(self) -> None:
        fonts = FontReport(self.pdf_path, 1).as_dict()["fonts"]
        faces = {(f["font"], f["size"], f["bold"]) for f in fonts}
        self.assertEqual({("Helvetica-Bold", 16.0, True), ("Helvetica", 10.0, False),
                          ("Helvetica-Bold", 12.0, True)}, faces)

    def test_the_sample_is_text_set_in_that_face(self) -> None:
        fonts = FontReport(self.pdf_path, 1).as_dict()["fonts"]
        by_size = {f["size"]: f["sample"] for f in fonts}
        self.assertEqual("Chapter One", by_size[16.0])

    def test_a_page_out_of_range_is_refused_as_a_filter_error(self) -> None:
        with self.assertRaises(FilterError):
            FontReport(self.pdf_path, 4).as_dict()


class TestOutlineSuggestion(SuggestTestCase):
    def test_each_filter_yields_entries_at_its_level(self) -> None:
        self.assertEqual([{"level": 1, "title": "Chapter One", "page": 1},
                          {"level": 2, "title": "1.1 First Section", "page": 1},
                          {"level": 1, "title": "Chapter Two: A Title Wrapped Over Two Lines", "page": 2},
                          {"level": 2, "title": "2.1 Second Section", "page": 3},
                          {"level": 2, "title": "2.2 Third Section", "page": 3}],
                         self.suggested(CHAPTER_FILTER, SECTION_FILTER))

    def test_consecutive_matching_lines_on_one_page_merge_into_one_title(self) -> None:
        titles = [e["title"] for e in self.suggested(CHAPTER_FILTER)]
        self.assertIn("Chapter Two: A Title Wrapped Over Two Lines", titles)

    def test_a_line_mixing_a_heading_font_with_another_font_is_not_an_entry(self) -> None:
        titles = [e["title"] for e in self.suggested(CHAPTER_FILTER, "NimbusSans-Regular:16:2")]
        self.assertFalse([t for t in titles if t.startswith("Mixed")])

    def test_pages_are_one_based_file_pages(self) -> None:
        self.assertEqual([1, 2], [e["page"] for e in self.suggested(CHAPTER_FILTER)])

    def test_a_filter_matching_no_span_yields_no_entries(self) -> None:
        self.assertEqual([], self.suggested("Times-Roman:9:1"))

    def test_the_suggestion_leaves_the_outline_untouched(self) -> None:
        self.suggested(CHAPTER_FILTER)
        with pymupdf.open(self.pdf_path) as doc:
            self.assertEqual([], doc.get_toc())


class TestFontFilter(unittest.TestCase):
    def test_a_spec_parses_into_font_size_and_level(self) -> None:
        self.assertEqual(FontFilter("Helvetica-Bold", 16.0, 1), FontFilter.parsed(CHAPTER_FILTER))

    def test_a_font_name_carrying_a_colon_is_kept_whole(self) -> None:
        self.assertEqual("ABCDEF+Times:Bold", FontFilter.parsed("ABCDEF+Times:Bold:11.5:2").font)

    def test_a_spec_without_three_parts_is_rejected(self) -> None:
        with self.assertRaises(FilterError):
            FontFilter.parsed("Helvetica-Bold:16")

    def test_a_non_numeric_size_is_rejected(self) -> None:
        with self.assertRaises(FilterError):
            FontFilter.parsed("Helvetica-Bold:big:1")

    def test_a_level_below_one_is_rejected(self) -> None:
        with self.assertRaises(FilterError):
            FontFilter.parsed("Helvetica-Bold:16:0")


class TestSuggestCommand(SuggestTestCase):
    def test_the_command_prints_the_entry_list_toc_write_accepts(self) -> None:
        printed = SilentCommand(TocCommands().suggest).run(pdf="styled.pdf", filter=[CHAPTER_FILTER], out=None)
        self.assertEqual([{"level": 1, "title": "Chapter One", "page": 1},
                          {"level": 1, "title": "Chapter Two: A Title Wrapped Over Two Lines", "page": 2}],
                         json.loads(printed))

    def test_a_relative_out_writes_the_same_list_under_the_scratch_directory(self) -> None:
        printed = SilentCommand(TocCommands().suggest).run(pdf="styled.pdf", filter=[CHAPTER_FILTER],
                                                           out="styled.entries.json")
        written = (vault.SCRATCH_DIR / "styled.entries.json").read_text(encoding="utf-8")
        self.assertEqual(json.loads(printed), json.loads(written))

    def test_an_absolute_out_inside_the_scratch_directory_is_written(self) -> None:
        out = vault.SCRATCH_DIR / "nested" / "styled.entries.json"
        printed = SilentCommand(TocCommands().suggest).run(pdf="styled.pdf", filter=[CHAPTER_FILTER], out=str(out))
        self.assertEqual(json.loads(printed), json.loads(out.read_text(encoding="utf-8")))

    def test_an_absolute_out_outside_the_scratch_directory_is_refused(self) -> None:
        out = self.vault.named("styled.entries.json")
        with self.assertRaises(SystemExit) as raised:
            SilentCommand(TocCommands().suggest).run(pdf="styled.pdf", filter=[CHAPTER_FILTER], out=str(out))
        self.assertIn("scratch directory", str(raised.exception))

    def test_a_refused_absolute_out_is_not_written(self) -> None:
        out = self.vault.named("styled.entries.json")
        with self.assertRaises(SystemExit):
            SilentCommand(TocCommands().suggest).run(pdf="styled.pdf", filter=[CHAPTER_FILTER], out=str(out))
        self.assertFalse(out.exists())

    def test_a_relative_out_escaping_the_scratch_directory_is_refused(self) -> None:
        with self.assertRaises(SystemExit):
            SilentCommand(TocCommands().suggest).run(pdf="styled.pdf", filter=[CHAPTER_FILTER],
                                                     out="../styled.entries.json")
        self.assertFalse(self.vault.named("styled.entries.json").exists())

    def test_the_fonts_command_names_the_page_it_read(self) -> None:
        printed = SilentCommand(TocCommands().fonts).run(pdf="styled.pdf", page=2)
        self.assertEqual(2, json.loads(printed)["page"])


if __name__ == "__main__":
    unittest.main()
