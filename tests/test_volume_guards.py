from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from unittest import mock

from _support import LiveTree

LiveTree.activate()

import pymupdf
from _volumes.apparatus_ranges import VolumeApparatus
from _volumes.cli import CommandLine
from _volumes.contents import VolumeContents
from _volumes.document import VolumeDocument
from _volumes.extraction import AppendedRange, ChapterExtraction, ChosenChapter, PageRange
from _vaults import TempVault, TextPdf

PATCHED_DIRS = ("INBOX_DIR", "LIBRARY_DIR", "VOLUMES_DIR", "CORPUS_DIR")
OUTLINE = [[1, "Chapter One", 1], [1, "Chapter Two", 2]]
CHAPTER_HEADING = "The Concept of Recognition"
FILED_BASENAME = "Pippin - 2008 - The Concept of Recognition"


class TestVolumeContents(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault(*PATCHED_DIRS).activate()
        self.addCleanup(self.vault.discard)

    def chapters(self, outline: list, pages: int = 2, max_level: int | None = None):
        path = TextPdf(self.vault.volumes / "collected.pdf", pages=pages, outline=outline).write()
        return VolumeContents(VolumeDocument.read(path), max_level=max_level).chapters()

    def headings(self, outline: list) -> list[str]:
        return [chapter.heading for chapter in self.chapters(outline)]

    def file_pages(self, outline: list, pages: int) -> list[str]:
        return [chapter.as_json()["file_pages"] for chapter in self.chapters(outline, pages, max_level=1)]

    def test_front_matter_is_not_a_chapter(self) -> None:
        self.assertEqual(["Chapter One"], self.headings([[1, "Note to the Reader", 1], [1, "Chapter One", 2]]))

    def test_the_index_is_not_a_chapter(self) -> None:
        self.assertEqual(["Chapter One"], self.headings([[1, "Chapter One", 1], [1, "Index", 2]]))

    def test_a_collected_bibliography_is_not_a_chapter(self) -> None:
        outline = [[1, "Chapter One", 1], [1, "Bibliographical References", 2]]
        self.assertEqual(["Chapter One"], self.headings(outline))

    def test_a_chapter_runs_to_the_next_opening_at_its_level_or_above(self) -> None:
        outline = [[1, "One", 1], [2, "One point one", 2], [1, "Two", 3]]
        self.assertEqual(["1-2", "3-4"], self.file_pages(outline, pages=4))

    def test_the_last_chapter_runs_to_the_page_count(self) -> None:
        self.assertEqual(["1-3"], self.file_pages([[1, "One", 1]], pages=3))


class TestVolumeApparatus(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault(*PATCHED_DIRS).activate()
        self.addCleanup(self.vault.discard)

    def sections(self, outline: list) -> list[tuple[str, str]]:
        path = TextPdf(self.vault.volumes / "collected.pdf", pages=2, outline=outline).write()
        return [(section.kind, section.title) for section in VolumeApparatus(VolumeDocument.read(path)).sections()]

    def test_a_collected_bibliography_is_found(self) -> None:
        outline = [[1, "Chapter One", 1], [1, "Bibliographical References", 2]]
        self.assertEqual([("bibliography", "Bibliographical References")], self.sections(outline))

    def test_collected_endnotes_are_found(self) -> None:
        self.assertEqual([("endnotes", "Notes")], self.sections([[1, "Chapter One", 1], [1, "Notes", 2]]))

    def test_collected_endnotes_headed_in_any_language_of_the_vault_are_found(self) -> None:
        for heading in ("Anmerkungen", "Noten", "Endnote", "Notes to the Text"):
            with self.subTest(heading=heading):
                self.assertEqual([("endnotes", heading)], self.sections([[1, "Chapter One", 1], [1, heading, 2]]))

    def test_notes_on_contributors_is_not_endnotes(self) -> None:
        self.assertEqual([], self.sections([[1, "Chapter One", 1], [1, "Notes on Contributors", 2]]))

    def test_a_chapter_title_naming_reference_is_not_a_bibliography(self) -> None:
        outline = [[1, "Essay 15: Reality without Reference", 1], [1, "Chapter Two", 2]]
        self.assertEqual([], self.sections(outline))


class TestExtractingWithAppendedRanges(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault(*PATCHED_DIRS).activate()
        self.addCleanup(self.vault.discard)
        path = TextPdf(self.vault.volumes / "collected.pdf", pages=2, outline=OUTLINE).write()
        self.source = VolumeDocument.read(path)

    def extraction(self, appended: list) -> ChapterExtraction:
        return ChapterExtraction(self.source, ChosenChapter(PageRange(1, 1), "Chapter One", tuple(appended)))

    def test_an_appended_range_adds_its_pages(self) -> None:
        plan = self.extraction([AppendedRange("bibliography: Refs", PageRange(2, 2))]).plan()
        self.assertEqual((2, [{"label": "bibliography: Refs", "file_pages": "2-2", "page_count": 1}]),
                         (plan["page_count"], plan["appended"]))

    def test_the_written_pdf_carries_the_chapter_then_the_appended_pages(self) -> None:
        self.extraction([AppendedRange("bibliography: Refs", PageRange(2, 2))]).write()
        with pymupdf.open(self.vault.inbox / "Chapter One.pdf") as written:
            texts = [written[index].get_text().strip() for index in range(written.page_count)]
        self.assertEqual(["Page 1", "Page 2"], [text[:len("Page 1")] for text in texts])

    def test_no_appended_range_writes_the_chapter_alone(self) -> None:
        self.extraction([]).write()
        with pymupdf.open(self.vault.inbox / "Chapter One.pdf") as written:
            self.assertEqual(1, written.page_count)

    def test_an_appended_range_past_the_end_is_refused_with_a_value_error(self) -> None:
        with self.assertRaises(ValueError):
            self.extraction([AppendedRange("bibliography: Refs", PageRange(9, 9))]).write()


class VolumesCommand:
    def __init__(self, *arguments: str) -> None:
        self._arguments = ["volumes.py", *arguments]

    def run(self) -> tuple[int, object]:
        buffer = io.StringIO()
        with mock.patch.object(sys, "argv", self._arguments), contextlib.redirect_stdout(buffer), \
                contextlib.redirect_stderr(io.StringIO()):
            code = self._exit_code()
        printed = buffer.getvalue()
        return code, json.loads(printed) if printed else None

    @staticmethod
    def _exit_code() -> int:
        try:
            CommandLine().run()
        except SystemExit as stop:
            return stop.code if isinstance(stop.code, int) else 1
        return 0


class TestAVolumeWithoutAnOutline(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault(*PATCHED_DIRS).activate()
        self.addCleanup(self.vault.discard)
        TextPdf(self.vault.volumes / "bare.pdf", pages=2, outline=[]).write()
        TextPdf(self.vault.volumes / "bookmarked.pdf", pages=2, outline=OUTLINE).write()

    def test_contents_exits_1_naming_the_missing_outline(self) -> None:
        self.assertEqual((1, {"error": "no outline: bookmark the volume first"}),
                         VolumesCommand("contents", "bare.pdf").run())

    def extract_bare(self) -> tuple[int, object]:
        return VolumesCommand("extract", "bare.pdf", "--range", "1-1", "--title", "Bare", "--apply").run()

    def test_extract_refuses_a_volume_without_an_outline(self) -> None:
        self.assertEqual((1, {"error": "no outline: bookmark the volume first"}), self.extract_bare())

    def test_a_refused_extract_writes_nothing(self) -> None:
        self.extract_bare()
        self.assertFalse((self.vault.inbox / "Bare.pdf").exists())

    def test_list_marks_the_outline_absent_or_present(self) -> None:
        code, rows = VolumesCommand("list").run()
        self.assertEqual((0, {"bare": "absent", "bookmarked": "present"}),
                         (code, {row["volume"]: row["outline"] for row in rows}))

    def test_contents_of_a_bookmarked_volume_lists_its_chapters(self) -> None:
        code, payload = VolumesCommand("contents", "bookmarked.pdf").run()
        self.assertEqual((0, ["Chapter One", "Chapter Two"]), (code, [c["title"] for c in payload["chapters"]]))


class TestVolumeDocument(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault(*PATCHED_DIRS).activate()
        self.addCleanup(self.vault.discard)

    def collected(self) -> VolumeDocument:
        return VolumeDocument.read(TextPdf(self.vault.volumes / "collected.pdf", pages=2, outline=OUTLINE).write())

    def test_the_page_count_is_read(self) -> None:
        self.assertEqual(2, self.collected().page_count)

    def test_the_outline_is_read_as_tuples(self) -> None:
        self.assertEqual(((1, "Chapter One", 1), (1, "Chapter Two", 2)), self.collected().outline)

    def test_an_outline_entry_pointing_before_the_first_page_is_dropped(self) -> None:
        outline = [[1, "Unplaced", -1], [1, "Chapter One", 1]]
        pdf = TextPdf(self.vault.volumes / "collected.pdf", pages=2, outline=outline).write()
        self.assertEqual(((1, "Chapter One", 1),), VolumeDocument.read(pdf).outline)


class TestExtractCommand(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault(*PATCHED_DIRS).activate()
        self.addCleanup(self.vault.discard)
        outline = [[1, "Chapter One", 1], [1, "Bibliography", 2]]
        TextPdf(self.vault.volumes / "collected.pdf", pages=2, outline=outline).write()

    def extract(self, *flags: str) -> tuple[int, object]:
        return VolumesCommand("extract", "collected.pdf", "--range", "1-1", "--title", "X", *flags).run()

    def test_apply_refuses_a_destination_already_in_the_inbox(self) -> None:
        occupied = self.vault.inbox / "X.pdf"
        occupied.write_bytes(b"already here")
        code, _ = self.extract("--apply")
        self.assertEqual((1, b"already here"), (code, occupied.read_bytes()))

    def test_a_collected_bibliography_is_appended_unless_no_apparatus_is_passed(self) -> None:
        _, with_apparatus = self.extract()
        _, without = self.extract("--no-apparatus")
        self.assertEqual((["bibliography: Bibliography"], []),
                         ([item["label"] for item in with_apparatus["appended"]], without["appended"]))

    def test_a_malformed_range_exits_one(self) -> None:
        code, _ = VolumesCommand("extract", "collected.pdf", "--range", "3-1", "--title", "X").run()
        self.assertEqual(1, code)


if __name__ == "__main__":
    unittest.main()
