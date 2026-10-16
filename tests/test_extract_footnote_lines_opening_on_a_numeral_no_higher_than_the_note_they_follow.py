from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from test_extract_footnotes_the_engine_reads_as_a_page_footer import (
    FIRST_NOTE_BASELINE, FIRST_SENTENCE, SECOND_NOTE_BASELINE, SECOND_SENTENCE, EngineRegion, FooterCase, NotedPage,
    NotedPdf, body_block, notes_block,
)
from _extract.blocks import FOOTNOTE_KIND, DocumentBlocks, PageBlocks
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs

CITATION_OPENING = "21 Aristotle argues that matter persists through change (1.7.190a13-"
CITATION_CLOSING = "21). So it might be tempting to call it inert."
CROSS_REFERENCE_OPENING = "32 As Wright puts it in his critique. See also Chapter"
CROSS_REFERENCE_CLOSING = "1 in this volume, pp. 22, 29-30."
CARRIED_OPENING = "10 Jacobi tabulates the numbers n and i such that, for each prime p and"
CARRIED_CLOSING = "1 < n < p, n is a power of a primitive root."
NEXT_NOTE = "11 There is some circularity going on here."
CITATION_ENDING_ON_A_PAGE = "10 Hegel, my translation, see also SL:"
PAGE_OPENING_A_LINE = "11 (GW 21:9)."
NOTE_ELEVEN = "For the distinction between objective and subjective logic see SL: 38-43."
TWICE_READ_NOTE = "Sacks 2000, 302."
FIRST_LINE = EngineRegion(FIRST_NOTE_BASELINE, FIRST_NOTE_BASELINE)
SECOND_LINE = EngineRegion(SECOND_NOTE_BASELINE, SECOND_NOTE_BASELINE)


def line_blocks(file_page: int, first: str, second: str) -> list:
    return [FIRST_LINE.block(file_page, FOOTNOTE_KIND, f"<p>{first}</p>"),
            SECOND_LINE.block(file_page, FOOTNOTE_KIND, f"<p>{second}</p>")]


def unnumbered(line: str) -> str:
    return line.split(" ", 1)[1]


class TestFootnoteLinesOpeningOnANumeralNoHigherThanTheNoteTheyFollow(FooterCase):
    def definitions(self, pages: list[NotedPage], engine_pages: list[PageBlocks]) -> list[tuple[int, str]]:
        return [(definition.label, definition.text) for definition in self.built(pages, engine_pages).definitions()]

    def test_a_line_opening_on_the_numeral_of_the_note_it_continues_stays_in_that_note(self) -> None:
        page = NotedPage(FIRST_SENTENCE, "21", (CITATION_OPENING, CITATION_CLOSING))
        engine_page = PageBlocks(1, [body_block(1, FIRST_SENTENCE, "<sup>21</sup>"),
                                     notes_block(1, FOOTNOTE_KIND, f"{CITATION_OPENING} {CITATION_CLOSING}")])
        self.assertEqual([(21, f"{unnumbered(CITATION_OPENING)} {CITATION_CLOSING}")],
                         self.definitions([page], [engine_page]))

    def test_a_line_opening_on_a_lower_numeral_no_mark_raises_stays_in_the_note_above(self) -> None:
        page = NotedPage(FIRST_SENTENCE, "32", (CROSS_REFERENCE_OPENING, CROSS_REFERENCE_CLOSING))
        engine_page = PageBlocks(1, [body_block(1, FIRST_SENTENCE, "<sup>32</sup>"),
                                     *line_blocks(1, CROSS_REFERENCE_OPENING, CROSS_REFERENCE_CLOSING)])
        self.assertEqual([(32, f"{unnumbered(CROSS_REFERENCE_OPENING)} {CROSS_REFERENCE_CLOSING}")],
                         self.definitions([page], [engine_page]))

    def test_a_page_opening_on_a_lower_numeral_no_mark_raises_continues_the_note_of_the_page_before(self) -> None:
        pages = [NotedPage(FIRST_SENTENCE, "10", (CARRIED_OPENING,)),
                 NotedPage(SECOND_SENTENCE, "11", (CARRIED_CLOSING, NEXT_NOTE))]
        engine_pages = [PageBlocks(1, [body_block(1, FIRST_SENTENCE, "<sup>10</sup>"),
                                       FIRST_LINE.block(1, FOOTNOTE_KIND, f"<p>{CARRIED_OPENING}</p>")]),
                        PageBlocks(2, [body_block(2, SECOND_SENTENCE, "<sup>11</sup>"),
                                       *line_blocks(2, CARRIED_CLOSING, NEXT_NOTE)])]
        self.assertEqual([(10, f"{unnumbered(CARRIED_OPENING)} {CARRIED_CLOSING}"), (11, unnumbered(NEXT_NOTE))],
                         self.definitions(pages, engine_pages))


class TestFootnoteLinesRepeatingTheNumeralOfTheNoteAbove(unittest.TestCase):
    def pixel_read(self, marks: str, printed_lines: tuple[str, ...], read_notes: list[str]) -> list[tuple[int, str]]:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        layer = TextLayer(NotedPdf(Path(directory.name) / "notes.pdf",
                                   [NotedPage(FIRST_SENTENCE, "", printed_lines)]).write())
        self.addCleanup(layer.close)
        regions = (FIRST_LINE, SECOND_LINE)
        reading = PageBlocks(1, [body_block(1, FIRST_SENTENCE, marks)] + [
            region.block(1, FOOTNOTE_KIND, f"<p>{note}</p>") for region, note in zip(regions, read_notes)])
        inputs = StructureInputs(DocumentBlocks([reading]), [], WorkerReadings.none(), keep_everything())
        work = WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts(), pixel_pages=frozenset({1}))
        return [(definition.label, definition.text) for definition in NoteStructure(work, inputs).definitions()]

    def test_a_note_read_twice_is_defined_once(self) -> None:
        twice = f"<sup>9</sup> {TWICE_READ_NOTE}"
        self.assertEqual([(9, TWICE_READ_NOTE)],
                         self.pixel_read("<sup>9</sup>", (f"9 {TWICE_READ_NOTE}",), [twice, twice]))

    def test_a_note_after_a_closed_sentence_returns_the_earlier_line_of_its_numeral_to_the_note_before(self) -> None:
        read_notes = [f"<sup>10</sup> {unnumbered(CITATION_ENDING_ON_A_PAGE)} {PAGE_OPENING_A_LINE}",
                      f"<sup>11</sup> {NOTE_ELEVEN}"]
        self.assertEqual([(10, f"{unnumbered(CITATION_ENDING_ON_A_PAGE)} {PAGE_OPENING_A_LINE}"), (11, NOTE_ELEVEN)],
                         self.pixel_read("<sup>10</sup> and<sup>11</sup>",
                                         (f"{CITATION_ENDING_ON_A_PAGE} {PAGE_OPENING_A_LINE}", f"11 {NOTE_ELEVEN}"),
                                         read_notes))


if __name__ == "__main__":
    unittest.main()
