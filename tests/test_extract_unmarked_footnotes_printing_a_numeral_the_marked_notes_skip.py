from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import FakeFonts, FakeHyphens, keep_everything
from _extract.blocks import FOOTNOTE_KIND, TEXT_KIND, Block, DocumentBlocks, PageBlocks
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.readings import WorkerReadings
from _extract.structure import NoteStructure, StructureInputs, WorkInputs
from _extract.writer import NoteWriter

FONT = "helv"
BODY_SIZE = 10.0
NOTE_SIZE = 8.0
MARK_SIZE = 6.0
MARK_RISE = 4.0
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = 360.0
LINE_HALF_HEIGHT = 8.0
BODY_BASELINE = 100.0
FIRST_NOTE_BASELINE = 540.0
NOTE_PITCH = 40.0
SENTENCE = "The first claim is stated here."
MARK = "12"
MARKED_NOTE = "A note the first claim marks."
UNMARKED_NOTE = "A note whose mark the body lost."


@dataclass(frozen=True)
class MarkedNotePage:
    notes: tuple[str, ...]

    def write(self, path: Path) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            page.insert_text((LEFT, BODY_BASELINE), SENTENCE, fontsize=BODY_SIZE, fontname=FONT)
            mark_left = LEFT + pymupdf.get_text_length(SENTENCE, FONT, BODY_SIZE)
            page.insert_text((mark_left, BODY_BASELINE - MARK_RISE), MARK, fontsize=MARK_SIZE, fontname=FONT)
            for baseline, note in zip(self._note_baselines(), self.notes):
                page.insert_text((LEFT, baseline), note, fontsize=NOTE_SIZE, fontname=FONT)
            document.save(path)
        return path

    def engine_reading(self) -> list[PageBlocks]:
        body = engine_block(TEXT_KIND, f"<p>{SENTENCE}<sup>{MARK}</sup></p>", BODY_BASELINE)
        notes = [engine_block(FOOTNOTE_KIND, f"<p>{note}</p>", baseline)
                 for baseline, note in zip(self._note_baselines(), self.notes)]
        return [PageBlocks(1, [body, *notes])]

    def _note_baselines(self) -> list[float]:
        return [FIRST_NOTE_BASELINE + index * NOTE_PITCH for index in range(len(self.notes))]


def engine_block(kind: str, html: str, baseline: float) -> Block:
    box = (LEFT, baseline - LINE_HALF_HEIGHT, RIGHT, baseline + LINE_HALF_HEIGHT / 2)
    return Block(1, kind, html, box, {}, f"/page/1/{kind}/{baseline}")


def labelled_definitions(page: MarkedNotePage) -> list[tuple[int, str]]:
    with tempfile.TemporaryDirectory() as directory:
        layer = TextLayer(page.write(Path(directory) / "page.pdf"))
        try:
            inputs = StructureInputs(DocumentBlocks(page.engine_reading()), [], WorkerReadings.none(),
                                     keep_everything())
            structure = NoteStructure(WorkInputs(layer, BlockHtml(FakeHyphens()), FakeFonts()), inputs)
            NoteWriter().render(structure.elements(), structure.definitions())
            return [(definition.label, definition.text) for definition in structure.definitions()]
        finally:
            layer.close()


class TestUnmarkedFootnotesPrintingANumeralTheMarkedNotesSkip(unittest.TestCase):
    def test_an_unmarked_note_printing_a_skipped_numeral_is_labelled_with_it(self) -> None:
        page = MarkedNotePage((f"11 {UNMARKED_NOTE}", f"{MARK} {MARKED_NOTE}"))
        self.assertEqual([(12, MARKED_NOTE), (11, f"11. {UNMARKED_NOTE}")], labelled_definitions(page))

    def test_an_unmarked_note_opening_on_superscript_digits_is_labelled_with_their_numeral_printed_as_digits(
            self) -> None:
        page = MarkedNotePage((f"³ {UNMARKED_NOTE}", f"{MARK} {MARKED_NOTE}"))
        self.assertEqual([(12, MARKED_NOTE), (3, f"3. {UNMARKED_NOTE}")], labelled_definitions(page))

    def test_an_unmarked_note_printing_a_marked_notes_numeral_in_superscript_digits_is_labelled_past_the_marked_in_digits(
            self) -> None:
        page = MarkedNotePage((f"¹² {UNMARKED_NOTE}", f"{MARK} {MARKED_NOTE}"))
        self.assertEqual([(12, MARKED_NOTE), (13, f"12 {UNMARKED_NOTE}")], labelled_definitions(page))

    def test_an_unmarked_note_printing_a_numeral_past_the_marked_is_labelled_next_after_them(self) -> None:
        page = MarkedNotePage((f"{MARK} {MARKED_NOTE}", f"15 {UNMARKED_NOTE}"))
        self.assertEqual([(12, MARKED_NOTE), (13, f"15. {UNMARKED_NOTE}")], labelled_definitions(page))


if __name__ == "__main__":
    unittest.main()
