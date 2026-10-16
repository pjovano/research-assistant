from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _extract.elements import Heading, Paragraph
from _extract.endnotes import EndnoteSections
from _extract.footnotes import FootnoteLog

CHAPTER_WITH_NOTES = [Heading(1, "Chapter One", 1), Paragraph("Body.<sup>1</sup>", False, 1),
                      Heading(2, "Notes", 2), Paragraph("1. See Kant.", False, 2), Paragraph("2 Ibid.", False, 2)]
CHAPTER_WITHOUT_NOTE_FIVE = [Heading(1, "Chapter Two", 3), Paragraph("Body.<sup>5</sup>", False, 3),
                             Heading(2, "Notes", 4), Paragraph("1. See Hegel.", False, 4)]


def logged(entries: list[tuple]) -> FootnoteLog:
    log = FootnoteLog()
    for kind, file_page, number in entries:
        getattr(log, kind)(file_page, number)
    return log


class TestEndnoteSections(unittest.TestCase):
    def test_a_mark_the_next_notes_section_lists_is_explained(self) -> None:
        self.assertTrue(EndnoteSections(CHAPTER_WITH_NOTES).lists_mark(1, "2"))

    def test_a_mark_the_next_notes_section_does_not_list_is_not_explained(self) -> None:
        self.assertFalse(EndnoteSections(CHAPTER_WITH_NOTES).lists_mark(1, "7"))

    def test_a_mark_is_judged_by_its_own_chapters_notes_when_numbering_restarts(self) -> None:
        sections = EndnoteSections(CHAPTER_WITH_NOTES + CHAPTER_WITHOUT_NOTE_FIVE)
        self.assertFalse(sections.lists_mark(3, "2"))

    def test_a_notes_section_ends_at_the_next_heading_of_its_level_or_above(self) -> None:
        sections = EndnoteSections(CHAPTER_WITH_NOTES + CHAPTER_WITHOUT_NOTE_FIVE)
        self.assertEqual((True, False), (sections.holds_page(2), sections.holds_page(3)))

    def test_a_work_with_no_notes_section_explains_nothing(self) -> None:
        self.assertFalse(EndnoteSections([Paragraph("Body.<sup>1</sup>", False, 1)]).lists_mark(1, "1"))


class TestQuietLog(unittest.TestCase):
    def test_an_unpaired_mark_its_notes_section_lists_is_left_out_of_the_log(self) -> None:
        log = logged([("unpaired_mark", 1, "1"), ("unpaired_mark", 1, "7")])
        self.assertEqual(["file p. 1: mark 7 has no footnote on the page"],
                         log.entries_outside(EndnoteSections(CHAPTER_WITH_NOTES)))

    def test_an_orphan_footnote_inside_a_notes_section_is_left_out_of_the_log(self) -> None:
        log = logged([("orphan_definition", 2, "1"), ("orphan_definition", 1, None)])
        self.assertEqual(["file p. 1: footnote (unnumbered) has no mark on the page"],
                         log.entries_outside(EndnoteSections(CHAPTER_WITH_NOTES)))

    def test_the_full_log_still_names_every_entry(self) -> None:
        log = logged([("unpaired_mark", 1, "1"), ("orphan_definition", 2, "1")])
        self.assertEqual(2, len(log.entries()))


if __name__ == "__main__":
    unittest.main()
