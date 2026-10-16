from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from test_extract_footnotes_the_engine_reads_as_a_page_footer import (
    FIRST_NOTE_BASELINE, SECOND_NOTE_BASELINE, EngineRegion, FooterCase, NotedPage, body_block,
)
from _extract.blocks import FOOTNOTE_KIND, PageBlocks
from _extract.elements import Paragraph

FIRST_SENTENCE = "The earlier work is presupposed throughout."
SECOND_SENTENCE = "Its readers were puzzled by the argument."
CLOSING_SENTENCE = "The notes to the whole essay follow."
FIRST_NOTE = "References are to the standard editions."
SECOND_NOTE = "The firm implication is logical priority."
PAIRED_NOTE = "A note printed beneath its own mark."
NO_MARK = ""
NOTE_REGIONS = (EngineRegion(FIRST_NOTE_BASELINE, FIRST_NOTE_BASELINE),
                EngineRegion(SECOND_NOTE_BASELINE, SECOND_NOTE_BASELINE))


class NotesPrintedPagesAfterTheirMarks(FooterCase):
    def structure_of(self, pages: list[NotedPage]) -> None:
        engine_pages = [PageBlocks(file_page, self._engine_blocks(file_page, page))
                        for file_page, page in enumerate(pages, start=1)]
        self.structure = self.built(pages, engine_pages)

    @staticmethod
    def _engine_blocks(file_page: int, page: NotedPage) -> list:
        mark = f"<sup>{page.mark}</sup>" if page.mark else NO_MARK
        notes = [region.block(file_page, FOOTNOTE_KIND, f"<p>{note}</p>")
                 for region, note in zip(NOTE_REGIONS, page.note_lines)]
        return [body_block(file_page, page.sentence, mark), *notes]

    def paragraphs(self) -> list[str]:
        return [element.text for element in self.structure.elements() if isinstance(element, Paragraph)]

    def labelled_texts(self) -> list[tuple[int, str]]:
        return [(definition.label, definition.text) for definition in self.structure.definitions()]


class TestFootnotesPrintedPagesAfterTheirMarksWithNoFootnotePairedBetween(NotesPrintedPagesAfterTheirMarks):
    def setUp(self) -> None:
        self.structure_of([NotedPage(FIRST_SENTENCE, "1", ()), NotedPage(SECOND_SENTENCE, "2", ()),
                           NotedPage(CLOSING_SENTENCE, NO_MARK, (f"1 {FIRST_NOTE}", f"2 {SECOND_NOTE}"))])

    def test_each_note_takes_its_printed_numeral_as_its_label(self) -> None:
        self.assertEqual([(1, FIRST_NOTE), (2, SECOND_NOTE)], self.labelled_texts())

    def test_each_mark_on_an_earlier_page_links_to_its_note(self) -> None:
        self.assertEqual([f"{FIRST_SENTENCE}[^1]", f"{SECOND_SENTENCE}[^2]"], self.paragraphs()[:2])

    def test_neither_the_marks_nor_the_notes_are_logged_unpaired(self) -> None:
        self.assertEqual([], self.structure.footnote_log())


class TestFootnotesPrintedPagesAfterTheirMarksWithAFootnotePairedBetween(NotesPrintedPagesAfterTheirMarks):
    def setUp(self) -> None:
        self.structure_of([NotedPage(FIRST_SENTENCE, "2", ()),
                           NotedPage(SECOND_SENTENCE, "1", (f"1 {PAIRED_NOTE}",)),
                           NotedPage(CLOSING_SENTENCE, NO_MARK, (f"2 {SECOND_NOTE}",))])

    def test_the_note_stays_unmarked_keeping_its_printed_numeral(self) -> None:
        self.assertIn(f"2. {SECOND_NOTE}", [text for _label, text in self.labelled_texts()])

    def test_the_mark_before_the_paired_footnote_stays_unlinked(self) -> None:
        self.assertEqual(f"{FIRST_SENTENCE}<sup>2</sup>", self.paragraphs()[0])


if __name__ == "__main__":
    unittest.main()
